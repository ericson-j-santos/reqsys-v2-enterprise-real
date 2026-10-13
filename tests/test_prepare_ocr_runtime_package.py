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


def test_prepare_delivers_closed_bundle_and_external_toolchain_evidence(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "ocr_distribution_evidence.py").write_text("# fixture\n")
    lock = tmp_path / "lock.json"
    sha = "a" * 40
    lock.write_text(json.dumps({
        "repository": "ericson-j-santos/ocr-evidence-engine",
        "sha": sha,
        "package": "ocr-evidence-engine",
        "module": "ocr_evidencia",
        "version": "1.2.0",
    }))
    toolchain_path = tmp_path / "toolchain.json"
    toolchain_path.write_text("{}")
    toolchain = {
        "python": "3.12.15", "pip": "26.1.2", "setuptools": "80.9.0",
        "wheel": "0.45.1", "packaging": "25.0",
    }
    monkeypatch.setattr(module, "_load_toolchain", lambda _: toolchain)
    monkeypatch.setattr(module, "_git_head", lambda _: sha)
    monkeypatch.setattr(
        module, "_git",
        lambda _source, *args: "1700000000" if args[0] == "show" else "",
    )

    def fake_run(args, **_kwargs):
        wheel_dir = Path(args[args.index("--wheel-dir") + 1])
        wheel_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_dir / "ocr_evidencia-1.2.0-py3-none-any.whl", "w") as zf:
            zf.writestr("ocr_evidencia/__init__.py", b"__version__='1.2.0'\n")
        return module.subprocess.CompletedProcess(args, 0)

    def fake_evidence(_script, command, output, _repository, _sha, _env):
        if command == "verify":
            return
        wheel = module._single_wheel(output)
        digest = module.hashlib.sha256(wheel.read_bytes()).hexdigest()
        manifest = f"{digest}  {wheel.name}\n"
        (output / "MANIFEST.sha256").write_text(manifest)
        (output / "SHA256SUMS").write_text(manifest)
        (output / "provenance.json").write_text(json.dumps({
            "package": {"name": "ocr-evidence-engine", "version": "1.2.0"},
            "files": [{"filename": wheel.name, "sha256": digest}],
        }))

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_run_evidence", fake_evidence)
    bundle = tmp_path / "bundle"
    evidence = tmp_path / "artifacts" / "toolchain.json"

    result = module.prepare(lock, source, bundle, toolchain_path, None, evidence)

    assert result["sha"] == sha
    assert sorted(path.name for path in bundle.iterdir()) == [
        "MANIFEST.sha256",
        "SHA256SUMS",
        "ocr_evidencia-1.2.0-py3-none-any.whl",
        "provenance.json",
    ]
    assert not (bundle / "build-toolchain.json").exists()
    assert json.loads(evidence.read_text())["toolchain"] == toolchain


def test_reproducibility_report_records_both_builds_and_negative_control(tmp_path: Path):
    first = _bundle(tmp_path / "first")
    second = tmp_path / "second"
    module.shutil.copytree(first, second)
    report = module.reproducibility_report(
        first, second, "a" * 40, {"python": "3.12.15"}, True
    )
    assert report["build_a"] == report["build_b"]
    assert report["byte_identical"] is True
    assert report["negative_control_detected"] is True
