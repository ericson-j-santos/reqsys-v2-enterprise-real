import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config" / "ocr-engine-lock.json"
TOOLCHAIN = ROOT / "config" / "ocr-build-toolchain.json"
ACTION = ROOT / ".github" / "actions" / "prepare-ocr-runtime" / "action.yml"
DEV_WORKFLOW = ROOT / ".github" / "workflows" / "fly-dev-fast-deploy.yml"
ENTERPRISE_WORKFLOW = ROOT / ".github" / "workflows" / "fly-enterprise-sync.yml"
BENCHMARK_WORKFLOW = ROOT / ".github" / "workflows" / "ocr-benchmark.yml"


def _yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_runtime_lock_is_private_repo_full_sha_and_expected_version() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assert lock["repository"] == "ericson-j-santos/ocr-evidence-engine"
    assert lock["sha"] == "15dd067032d7c55e22186ef3587c0d694d0392fd"
    assert re.fullmatch(r"[0-9a-f]{40}", lock["sha"])
    assert lock["package"] == "ocr-evidence-engine"
    assert lock["module"] == "ocr_evidencia"
    assert lock["version"] == "1.2.0"


def test_prepare_action_uses_ephemeral_read_only_app_token_for_two_clean_trees() -> None:
    steps = _yaml(ACTION)["runs"]["steps"]
    token = next(step for step in steps if step.get("id") == "app-token")
    checkouts = [step for step in steps if str(step.get("name", "")).startswith("Checkout limpo ")]
    assert token["uses"] == "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1"
    assert token["with"]["permission-contents"] == "read"
    assert token["with"]["repositories"].splitlines() == ["reqsys-v2-enterprise-real", "ocr-evidence-engine"]
    assert len(checkouts) == 2
    assert {step["with"]["path"] for step in checkouts} == {".external/ocr-evidence-engine-a", ".external/ocr-evidence-engine-b"}
    for checkout in checkouts:
        assert checkout["with"]["ref"] == "${{ steps.lock.outputs.sha }}"
        assert checkout["with"]["persist-credentials"] == "false"
    assert "permission-contents: write" not in ACTION.read_text()
    assert "GH_PAT" not in ACTION.read_text()


def test_prepare_script_generates_and_verifies_canonical_bundle() -> None:
    text = (ROOT / "scripts" / "prepare_ocr_runtime_package.py").read_text(encoding="utf-8")
    for value in ("ocr_distribution_evidence.py", '"generate"', '"verify"', "MANIFEST.sha256", "SHA256SUMS", "ocr_manifest_compatibility_mismatch", "ocr_source_sha_mismatch", "SOURCE_DATE_EPOCH", '"PYTHONHASHSEED": "0"', "--no-build-isolation", "compare_bundles"):
        assert value in text


def test_prepare_action_pins_and_records_complete_toolchain() -> None:
    expected = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))
    text = ACTION.read_text(encoding="utf-8")
    assert expected == {"python": "3.12.15", "pip": "26.1.2", "setuptools": "80.9.0", "wheel": "0.45.1", "packaging": "25.0"}
    for name, version in expected.items():
        if name != "python":
            assert f"{name}=={version}" in text
    assert "data['files'][0]['sha256']" in text
    assert "data['wheel_sha256']" not in text


def test_dockerfile_fails_closed_and_removes_local_copy_when_external_is_required() -> None:
    text = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    for value in ("ARG OCR_EXTERNAL_PACKAGE_REQUIRED=0", 'test "$wheel_count" = "1"', "provenance.json", "MANIFEST.sha256", "SHA256SUMS", 'd["schema_version"]=="1.1.0"', "actual==expected_names", "OCR_ENGINE_SHA", "OCR_ENGINE_VERSION", "rm -rf /app/ocr_evidencia", "site-packages"):
        assert value in text
    assert "GITHUB_TOKEN" not in text
    assert "REQSYS_STACK_REBASE_PRIVATE_KEY" not in text


def test_canonical_fly_workflows_prepare_package_and_require_external_runtime() -> None:
    for path in (DEV_WORKFLOW, ENTERPRISE_WORKFLOW):
        text = path.read_text(encoding="utf-8")
        assert "uses: ./.github/actions/prepare-ocr-runtime" in text
        assert 'OCR_EXTERNAL_PACKAGE_REQUIRED=1' in text
        assert 'OCR_ENGINE_SHA=${{ steps.ocr-runtime.outputs.ocr-sha }}' in text
        assert 'OCR_ENGINE_VERSION=${{ steps.ocr-runtime.outputs.ocr-version }}' in text


def test_benchmark_builds_real_image_with_negative_control_first() -> None:
    job = _yaml(BENCHMARK_WORKFLOW)["jobs"]["external-runtime-image-contract"]
    names = [step.get("name", "") for step in job["steps"]]
    assert names.index("Controle negativo: build externo sem wheel deve falhar") < names.index("Preparar pacote OCR externo") < names.index("Build da imagem com OCR externo obrigatório") < names.index("Provar import externo dentro da imagem")
    text = BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
    assert "docker build" in text
    assert "docker run --rm --entrypoint python" in text
    assert "local_ocr_copy_present" in text


def test_benchmark_publishes_complete_reproducible_runtime_bundle() -> None:
    job = _yaml(BENCHMARK_WORKFLOW)["jobs"]["external-package-contract"]
    steps = job["steps"]
    names = [step.get("name", "") for step in steps]
    validate_name = "Validar evidência durável do pacote OCR"
    upload_name = "Publicar bundle OCR reproduzível"

    assert names.index("Preparar pacote OCR canônico e reproduzível") < names.index(
        "Provar origem externa e executar contratos do ReqSys"
    ) < names.index(validate_name) < names.index(upload_name)

    validation = next(step for step in steps if step.get("name") == validate_name)
    validation_script = validation["run"]
    for value in (
        'report.get("source_sha") != lock["sha"]',
        'report.get("byte_identical") is not True',
        'report.get("negative_control_detected") is not True',
        'report.get("build_a") != report.get("build_b")',
        "ocr_durable_artifact_hash_mismatch",
        "MANIFEST.sha256",
        "SHA256SUMS",
        "provenance.json",
    ):
        assert value in validation_script

    upload = next(step for step in steps if step.get("name") == upload_name)
    assert upload["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert upload["with"]["name"] == "ocr-runtime-package-${{ github.sha }}"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["retention-days"] == "90"
    assert set(upload["with"]["path"].splitlines()) == {
        "backend/vendor/ocr-evidence-engine/*.whl",
        "backend/vendor/ocr-evidence-engine/MANIFEST.sha256",
        "backend/vendor/ocr-evidence-engine/SHA256SUMS",
        "backend/vendor/ocr-evidence-engine/provenance.json",
        "artifacts/ocr-build-toolchain.json",
        "artifacts/ocr-reproducibility-report.json",
    }
