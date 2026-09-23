from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ocr-benchmark.yml"
PINNED_SHA = "15209941c4ddbf52da62cedc866510592b3172ee"


def _workflow() -> dict:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _external_job() -> dict:
    return _workflow()["jobs"]["external-package-contract"]


def _step(step_id: str) -> dict:
    steps = _external_job()["steps"]
    return next(step for step in steps if step.get("id") == step_id)


def test_external_ocr_dependency_is_pinned_to_immutable_sha() -> None:
    workflow = _workflow()

    assert workflow["env"]["OCR_ENGINE_SHA"] == PINNED_SHA
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "ocr-evidence-engine.git@main" not in text
    assert "ref: ${{ env.OCR_ENGINE_SHA }}" in text


def test_governed_app_requests_only_read_access_to_exact_repositories() -> None:
    token_step = _step("app-token")

    assert token_step["uses"] == "actions/create-github-app-token@v2"
    assert token_step["with"]["permission-contents"] == "read"
    assert token_step["with"]["repositories"].splitlines() == [
        "reqsys-v2-enterprise-real",
        "ocr-evidence-engine",
    ]
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "permission-contents: write" not in text
    assert "GH_PAT" not in text
    assert "personal access token" not in text.lower()


def test_external_contract_has_negative_control_before_authentication() -> None:
    steps = _external_job()["steps"]
    names = [str(step.get("name", "")) for step in steps]

    isolate = names.index("Isolar a cópia local e provar ausência do pacote")
    token = names.index("Emitir token temporário somente leitura")
    checkout = names.index("Checkout do OCR privado no SHA pinado")

    assert isolate < token < checkout
    body = steps[isolate]["run"]
    assert 'mv backend/ocr_evidencia "$RUNNER_TEMP/ocr_evidencia_local_copy"' in body
    assert "python -c 'import ocr_evidencia'" in body
    assert 'test "$rc" -ne 0' in body


def test_external_contract_proves_installed_origin_and_consumer_tests() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'test "$actual" = "$OCR_ENGINE_SHA"' in text
    assert "site-packages" in text
    assert "ocr_origin_is_local_copy" in text
    assert "ocr_origin_is_checkout_not_installed_package" in text
    assert 'ocr_evidencia.__version__ != "1.2.0"' in text
    assert "python -m pytest -q backend/ocr_tests" in text
