#!/usr/bin/env python3
"""Prepara o bundle OCR externo e valida a evidência canônica do provedor."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


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


def _git_head(source: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


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
    subprocess.run(args, check=True)


def prepare(lock_path: Path, source: Path, output_dir: Path) -> dict[str, str]:
    lock = _load_lock(lock_path)
    source = source.resolve()
    if not source.is_dir():
        raise RuntimePackageError(f"ocr_source_missing:{source}")

    actual_sha = _git_head(source)
    expected_sha = str(lock["sha"])
    if actual_sha != expected_sha:
        raise RuntimePackageError(
            f"ocr_source_sha_mismatch:expected={expected_sha}:actual={actual_sha}"
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
                "--wheel-dir",
                str(wheel_dir),
                str(source),
            ],
            check=True,
        )
        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimePackageError(f"ocr_wheel_count_invalid:{len(wheels)}")
        shutil.copy2(wheels[0], output_dir / wheels[0].name)

    repository = str(lock["repository"])
    _run_evidence(evidence_script, "generate", output_dir, repository, expected_sha)
    _run_evidence(evidence_script, "verify", output_dir, repository, expected_sha)

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
    parser.add_argument("--source", default=".external/ocr-evidence-engine")
    parser.add_argument(
        "--output-dir", default="backend/vendor/ocr-evidence-engine"
    )
    args = parser.parse_args()
    try:
        prepare(Path(args.lock), Path(args.source), Path(args.output_dir))
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
