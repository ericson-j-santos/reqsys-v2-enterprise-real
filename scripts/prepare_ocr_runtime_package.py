#!/usr/bin/env python3
"""Prepara o bundle OCR externo e valida sua reprodutibilidade binária."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

REPRODUCIBLE_FILES = ("MANIFEST.sha256", "SHA256SUMS")


class RuntimePackageError(RuntimeError):
    """Falha fechada ao preparar o pacote OCR externo."""


def _load_lock(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"repository", "sha", "package", "module", "version"}
    missing = sorted(required - set(data))
    if missing:
        raise RuntimePackageError(f"ocr_lock_missing_fields:{','.join(missing)}")
    sha = str(data["sha"])
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimePackageError("ocr_lock_sha_must_be_full_commit")
    return data


def _git(source: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _git_head(source: Path) -> str:
    return _git(source, "rev-parse", "HEAD")


def _git_commit_epoch(source: Path, expected_sha: str) -> str:
    epoch = _git(source, "show", "-s", "--format=%ct", expected_sha)
    if not re.fullmatch(r"[1-9][0-9]{8,}", epoch):
        raise RuntimePackageError("ocr_source_date_epoch_invalid")
    return epoch


def _load_toolchain(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"python", "pip", "setuptools", "wheel", "packaging"}
    missing = sorted(required - set(data))
    if missing:
        raise RuntimePackageError(f"ocr_toolchain_missing_fields:{','.join(missing)}")
    expected_python = str(data["python"])
    observed_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if observed_python != expected_python:
        raise RuntimePackageError(
            f"ocr_toolchain_python_mismatch:expected={expected_python}:actual={observed_python}"
        )
    observed = {
        name: importlib.metadata.version(name)
        for name in ("pip", "setuptools", "wheel", "packaging")
    }
    for name, version in observed.items():
        expected = str(data[name])
        if version != expected:
            raise RuntimePackageError(
                f"ocr_toolchain_version_mismatch:{name}:expected={expected}:actual={version}"
            )
    return {"python": observed_python, **observed}


def _normalize_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _clear_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for entry in output_dir.iterdir():
        if entry.is_symlink() or entry.is_file():
            entry.unlink()
        else:
            raise RuntimePackageError(f"ocr_output_entry_not_file:{entry.name}")


def _run_evidence(
    evidence_script: Path,
    command: str,
    output_dir: Path,
    repository: str,
    sha: str,
    env: dict[str, str],
) -> None:
    if command == "generate":
        args = [
            sys.executable,
            str(evidence_script),
            "generate",
            "--bundle-dir",
            str(output_dir),
            "--repository",
            repository,
            "--git-sha",
            sha,
        ]
    else:
        args = [
            sys.executable,
            str(evidence_script),
            "verify",
            "--bundle-dir",
            str(output_dir),
            "--expected-repository",
            repository,
            "--expected-git-sha",
            sha,
        ]
    subprocess.run(args, check=True, env=env)


def _single_wheel(directory: Path) -> Path:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimePackageError(f"ocr_wheel_count_invalid:{len(wheels)}")
    return wheels[0]


def _zip_difference(first: Path, second: Path) -> str:
    try:
        with zipfile.ZipFile(first) as left, zipfile.ZipFile(second) as right:
            left_names = sorted(left.namelist())
            right_names = sorted(right.namelist())
            if left_names != right_names:
                return "zip_member_set"
            for name in left_names:
                if left.read(name) != right.read(name):
                    return f"zip_member:{name}"
            return "zip_container_metadata"
    except zipfile.BadZipFile:
        return "invalid_zip"


def compare_bundles(first: Path, second: Path) -> dict[str, str]:
    left_wheel = _single_wheel(first)
    right_wheel = _single_wheel(second)
    required = (left_wheel.name, *REPRODUCIBLE_FILES)
    if right_wheel.name != left_wheel.name:
        raise RuntimePackageError("ocr_reproducibility_wheel_filename_mismatch")
    hashes: dict[str, str] = {}
    for name in required:
        left = first / name
        right = second / name
        if not left.is_file() or not right.is_file():
            raise RuntimePackageError(f"ocr_reproducibility_file_missing:{name}")
        left_bytes = left.read_bytes()
        right_bytes = right.read_bytes()
        if left_bytes != right_bytes:
            detail = _zip_difference(left, right) if name.endswith(".whl") else "file_bytes"
            raise RuntimePackageError(f"ocr_reproducibility_mismatch:{name}:{detail}")
        hashes[name] = hashlib.sha256(left_bytes).hexdigest()
    return hashes


def prepare(
    lock_path: Path,
    source: Path,
    output_dir: Path,
    toolchain_path: Path = Path("config/ocr-build-toolchain.json"),
    compare_with: Path | None = None,
) -> dict[str, str]:
    lock = _load_lock(lock_path)
    toolchain = _load_toolchain(toolchain_path)
    source = source.resolve()
    if not source.is_dir():
        raise RuntimePackageError(f"ocr_source_missing:{source}")

    actual_sha = _git_head(source)
    expected_sha = str(lock["sha"])
    if actual_sha != expected_sha:
        raise RuntimePackageError(
            f"ocr_source_sha_mismatch:expected={expected_sha}:actual={actual_sha}"
        )
    if _git(source, "status", "--porcelain"):
        raise RuntimePackageError("ocr_source_not_clean")

    source_date_epoch = _git_commit_epoch(source, expected_sha)
    build_env = os.environ.copy()
    build_env.update(
        {
            "SOURCE_DATE_EPOCH": source_date_epoch,
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )

    evidence_script = source / "scripts" / "ocr_distribution_evidence.py"
    if not evidence_script.is_file():
        raise RuntimePackageError("ocr_distribution_evidence_missing")

    _clear_output_dir(output_dir)
    with tempfile.TemporaryDirectory(prefix="ocr-runtime-wheel-") as temp_dir:
        wheel_dir = Path(temp_dir)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--disable-pip-version-check",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_dir),
                str(source),
            ],
            check=True,
            env=build_env,
        )
        wheel = _single_wheel(wheel_dir)
        shutil.copyfile(wheel, output_dir / wheel.name)

    repository = str(lock["repository"])
    _run_evidence(
        evidence_script, "generate", output_dir, repository, expected_sha, build_env
    )
    _run_evidence(
        evidence_script, "verify", output_dir, repository, expected_sha, build_env
    )

    provenance = json.loads(
        (output_dir / "provenance.json").read_text(encoding="utf-8")
    )
    package = provenance["package"]
    file_entry = provenance["files"][0]
    if _normalize_package_name(str(package["name"])) != _normalize_package_name(
        str(lock["package"])
    ):
        raise RuntimePackageError(
            f"ocr_package_name_mismatch:expected={lock['package']}:actual={package['name']}"
        )
    if str(package["version"]) != str(lock["version"]):
        raise RuntimePackageError(
            f"ocr_package_version_mismatch:expected={lock['version']}:actual={package['version']}"
        )

    canonical = (output_dir / "MANIFEST.sha256").read_bytes()
    compatibility = (output_dir / "SHA256SUMS").read_bytes()
    if canonical != compatibility:
        raise RuntimePackageError("ocr_manifest_compatibility_mismatch")

    build_record = {
        "schema_version": "1.0",
        "source_sha": expected_sha,
        "source_date_epoch": source_date_epoch,
        "pythonhashseed": "0",
        "toolchain": toolchain,
    }
    (output_dir / "build-toolchain.json").write_text(
        json.dumps(build_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if compare_with is not None:
        hashes = compare_bundles(compare_with, output_dir)
        print(
            "OCR_REPRODUCIBLE_BUILDS_OK "
            f"wheel_sha256={hashes[str(file_entry['filename'])]}"
        )

    print(
        "OCR_RUNTIME_PACKAGE_READY "
        f"source_sha={expected_sha} version={package['version']} "
        f"wheel_sha256={file_entry['sha256']}"
    )
    return {
        "sha": expected_sha,
        "version": str(package["version"]),
        "wheel_sha256": str(file_entry["sha256"]),
        "wheel": str(file_entry["filename"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", default="config/ocr-engine-lock.json")
    parser.add_argument("--toolchain", default="config/ocr-build-toolchain.json")
    parser.add_argument("--source", default=".external/ocr-evidence-engine")
    parser.add_argument("--output-dir", default="backend/vendor/ocr-evidence-engine")
    parser.add_argument("--compare-with", default="")
    args = parser.parse_args()
    try:
        prepare(
            Path(args.lock),
            Path(args.source),
            Path(args.output_dir),
            Path(args.toolchain),
            Path(args.compare_with) if args.compare_with else None,
        )
        return 0
    except (
        RuntimePackageError,
        OSError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"OCR_RUNTIME_PACKAGE_BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
