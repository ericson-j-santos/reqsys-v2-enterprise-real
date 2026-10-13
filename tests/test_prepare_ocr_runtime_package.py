from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_ocr_runtime_package.py"
spec = importlib.util.spec_from_file_location("prepare_ocr_runtime_package", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _bundle(root: Path, payload: bytes = b"payload") -> Path:
    root.mkdir()
    wheel = root / "ocr_evidencia-1.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("ocr_evidencia/__init__.py", payload)
    digest = module.hashlib.sha256(wheel.read_bytes()).hexdigest()
    manifest = f"{digest}  {wheel.name}\n".encode()
    (root / "MANIFEST.sha256").write_bytes(manifest)
    (root / "SHA256SUMS").write_bytes(manifest)
    return root


def test_compare_bundles_accepts_byte_identical_outputs(tmp_path: Path):
    first = _bundle(tmp_path / "first")
    second = tmp_path / "second"
    module.shutil.copytree(first, second)
    result = module.compare_bundles(first, second)
    assert set(result) == {
        "ocr_evidencia-1.2.0-py3-none-any.whl",
        "MANIFEST.sha256",
        "SHA256SUMS",
    }


@pytest.mark.parametrize("name", ["MANIFEST.sha256", "SHA256SUMS"])
def test_compare_bundles_rejects_tampered_manifest(tmp_path: Path, name: str):
    first = _bundle(tmp_path / "first")
    second = tmp_path / "second"
    module.shutil.copytree(first, second)
    (second / name).write_bytes((second / name).read_bytes() + b"tampered")
    with pytest.raises(module.RuntimePackageError, match="ocr_reproducibility_mismatch"):
        module.compare_bundles(first, second)


def test_compare_bundles_reports_changed_zip_member(tmp_path: Path):
    first = _bundle(tmp_path / "first", b"one")
    second = _bundle(tmp_path / "second", b"two")
    with pytest.raises(
        module.RuntimePackageError,
        match=r"zip_member:ocr_evidencia/__init__\.py",
    ):
        module.compare_bundles(first, second)


def test_toolchain_lock_is_exact_and_complete():
    data = json.loads((ROOT / "config" / "ocr-build-toolchain.json").read_text())
    assert data == {
        "python": "3.12.15",
        "pip": "26.1.2",
        "setuptools": "80.9.0",
        "wheel": "0.45.1",
        "packaging": "25.0",
    }
