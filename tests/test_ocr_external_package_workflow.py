import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ocr-benchmark.yml"
ACTION = ROOT / ".github" / "actions" / "prepare-ocr-runtime" / "action.yml"
LOCK = ROOT / "config" / "ocr-engine-lock.json"


def _yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _external_job() -> dict:
    return _yaml(WORKFLOW)["jobs"]["external-package-contract"]


def test_external_ocr_dependency_is_pinned_to_immutable_sha() -> None:
    workflow = _yaml(WORKFLOW)
    action_text = ACTION.read_text(encoding="utf-8")
    assert workflow["env"]["OCR_ENGINE_SHA"] == json.loads(LOCK.read_text())["sha"]
    assert "ocr-evidence-engine.git@main" not in action_text
    assert action_text.count("ref: ${{ steps.lock.outputs.sha }}") == 2
    assert "uses: ./.github/actions/prepare-ocr-runtime" in WORKFLOW.read_text()


def test_governed_app_requests_only_read_access_to_exact_repositories() -> None:
    steps = _yaml(ACTION)["runs"]["steps"]
    token = next(step for step in steps if step.get("id") == "app-token")
    assert token["uses"] == "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1"
    assert token["with"]["permission-contents"] == "read"
    assert token["with"]["repositories"].splitlines() == ["reqsys-v2-enterprise-real", "ocr-evidence-engine"]
    combined = WORKFLOW.read_text() + ACTION.read_text()
    assert "permission-contents: write" not in combined
    assert "GH_PAT" not in combined
    assert "personal access token" not in combined.lower()


def test_external_contract_has_negative_control_before_authentication() -> None:
    consumer_steps = _external_job()["steps"]
    names = [str(step.get("name", "")) for step in consumer_steps]
    isolate = names.index("Isolar a cópia local e provar ausência do pacote")
    prepare = names.index("Preparar pacote OCR canônico e reproduzível")
    assert isolate < prepare
    body = consumer_steps[isolate]["run"]
    assert 'mv backend/ocr_evidencia "$RUNNER_TEMP/ocr_evidencia_local_copy"' in body
    assert "python -c 'import ocr_evidencia'" in body
    assert 'test "$rc" -ne 0' in body
    action_names = [str(step.get("name", "")) for step in _yaml(ACTION)["runs"]["steps"]]
    assert action_names.index("Emitir token temporário somente leitura") < action_names.index("Checkout limpo A do OCR no SHA do lock") < action_names.index("Checkout limpo B do OCR no SHA do lock")


def test_external_contract_proves_installed_origin_and_consumer_tests() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    action_text = ACTION.read_text(encoding="utf-8")
    assert 'test "${{ steps.ocr-package.outputs.ocr-sha }}" = "$OCR_ENGINE_SHA"' in text
    assert "backend/vendor/ocr-evidence-engine/*.whl" in text
    assert "site-packages" in text
    assert "ocr_origin_is_local_copy" in text
    assert "ocr_origin_is_checkout_not_installed_package" in text
    assert 'ocr_evidencia.__version__ != "1.2.0"' in text
    assert "python -m pytest -q backend/ocr_tests" in text
    assert "--compare-with" in action_text
    assert "OCR_REPRODUCIBILITY_NEGATIVE_CONTROL_OK" in action_text
