import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config" / "ocr-engine-lock.json"
ACTION = ROOT / ".github" / "actions" / "prepare-ocr-runtime" / "action.yml"
DEV_WORKFLOW = ROOT / ".github" / "workflows" / "fly-dev-fast-deploy.yml"
ENTERPRISE_WORKFLOW = ROOT / ".github" / "workflows" / "fly-enterprise-sync.yml"
BENCHMARK_WORKFLOW = ROOT / ".github" / "workflows" / "ocr-benchmark.yml"
PINNED_SHA = "15209941c4ddbf52da62cedc866510592b3172ee"


def _yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_runtime_lock_is_private_repo_full_sha_and_expected_version() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))

    assert lock["repository"] == "ericson-j-santos/ocr-evidence-engine"
    assert lock["sha"] == PINNED_SHA
    assert re.fullmatch(r"[0-9a-f]{40}", lock["sha"])
    assert lock["package"] == "ocr-evidence-engine"
    assert lock["module"] == "ocr_evidencia"
    assert lock["version"] == "1.2.0"


def test_prepare_action_uses_ephemeral_read_only_app_token() -> None:
    action = _yaml(ACTION)
    steps = action["runs"]["steps"]
    token = next(step for step in steps if step.get("id") == "app-token")
    checkout = next(
        step for step in steps if step.get("name") == "Checkout OCR privado no SHA do lock"
    )

    assert token["uses"] == "actions/create-github-app-token@v2"
    assert token["with"]["permission-contents"] == "read"
    assert token["with"]["repositories"].splitlines() == [
        "reqsys-v2-enterprise-real",
        "ocr-evidence-engine",
    ]
    assert checkout["with"]["ref"] == "${{ steps.lock.outputs.sha }}"
    assert checkout["with"]["persist-credentials"] == "false"
    text = ACTION.read_text(encoding="utf-8")
    assert "permission-contents: write" not in text
    assert "GH_PAT" not in text


def test_prepare_script_records_sha256_without_credentials() -> None:
    text = (ROOT / "scripts" / "prepare_ocr_runtime_package.py").read_text(
        encoding="utf-8"
    )

    assert "hashlib.sha256" in text
    assert '"credentials_embedded": False' in text
    assert "ocr_source_sha_mismatch" in text
    assert "pip" in text and "wheel" in text and "--no-deps" in text


def test_dockerfiles_fail_closed_and_remove_local_copy_when_external_is_required() -> None:
    for relative in ("backend/Dockerfile", "backend/Dockerfile.fly"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "ARG OCR_EXTERNAL_PACKAGE_REQUIRED=0" in text
        assert 'test "$wheel_count" = "1"' in text
        assert "provenance.json" in text
        assert "OCR_ENGINE_SHA" in text
        assert "OCR_ENGINE_VERSION" in text
        assert "rm -rf /app/ocr_evidencia" in text
        assert "site-packages" in text
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
    workflow = _yaml(BENCHMARK_WORKFLOW)
    job = workflow["jobs"]["external-runtime-image-contract"]
    names = [step.get("name", "") for step in job["steps"]]

    negative = names.index("Controle negativo: build externo sem wheel deve falhar")
    prepare = names.index("Preparar pacote OCR externo")
    positive = names.index("Build da imagem com OCR externo obrigatório")
    runtime = names.index("Provar import externo dentro da imagem")
    assert negative < prepare < positive < runtime

    text = BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
    assert "docker build" in text
    assert "docker run --rm --entrypoint python" in text
    assert "local_ocr_copy_present" in text
