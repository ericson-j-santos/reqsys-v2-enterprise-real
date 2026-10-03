#!/usr/bin/env python3
"""Prepara o pacote OCR externo para o contexto de build sem persistir credenciais."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
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


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise RuntimePackageError(
                f"ocr_wheel_metadata_count_invalid:{len(metadata_names)}"
            )
        metadata = archive.read(metadata_names[0]).decode("utf-8")
    name = version = ""
    for line in metadata.splitlines():
        if line.startswith("Name: "):
            name = line[6:].strip()
        elif line.startswith("Version: "):
            version = line[9:].strip()
    if not name or not version:
        raise RuntimePackageError("ocr_wheel_metadata_incomplete")
    return name, version


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    output_dir.mkdir(parents=True, exist_ok=True)
    for candidate in output_dir.glob("*.whl"):
        candidate.unlink()
    provenance_path = output_dir / "provenance.json"
    if provenance_path.exists():
        provenance_path.unlink()

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
        built_wheel = wheels[0]
        package_name, version = _wheel_metadata(built_wheel)
        if _normalize_package_name(package_name) != _normalize_package_name(
            str(lock["package"])
        ):
            raise RuntimePackageError(
                f"ocr_package_name_mismatch:expected={lock['package']}:actual={package_name}"
            )
        if version != str(lock["version"]):
            raise RuntimePackageError(
                f"ocr_package_version_mismatch:expected={lock['version']}:actual={version}"
            )

        destination = output_dir / built_wheel.name
        shutil.copy2(built_wheel, destination)

    wheel_sha256 = _sha256(destination)
    provenance = {
        "schema_version": "1.0.0",
        "repository": lock["repository"],
        "source_sha": expected_sha,
        "package": package_name,
        "module": lock["module"],
        "version": version,
        "wheel": destination.name,
        "wheel_sha256": wheel_sha256,
        "credentials_embedded": False,
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "OCR_RUNTIME_PACKAGE_READY "
        f"source_sha={expected_sha} version={version} wheel_sha256={wheel_sha256}"
    )
    return {
        "sha": expected_sha,
        "version": version,
        "wheel_sha256": wheel_sha256,
        "wheel": destination.name,
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
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"OCR_RUNTIME_PACKAGE_BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
