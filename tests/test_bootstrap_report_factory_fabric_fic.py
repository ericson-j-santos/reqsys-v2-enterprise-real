import importlib.util
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_report_factory_fabric_fic.py"
WORKFLOW = ROOT / ".github" / "workflows" / "report-factory-fabric-fic-bootstrap.yml"

SPEC = importlib.util.spec_from_file_location("bootstrap_report_factory_fabric_fic", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_contract_is_exact_and_environment_scoped() -> None:
    assert MODULE.CREDENTIAL_NAME == "reqsys-report-factory-development"
    assert MODULE.ISSUER == "https://token.actions.githubusercontent.com"
    assert MODULE.AUDIENCE == "api://AzureADTokenExchange"
    assert MODULE.SUBJECT == (
        "repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development"
    )


def test_workflow_requires_dispatch_and_literal_confirmation_for_apply() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert 'mode:' in text
    assert 'confirm:' in text
    assert "CRIAR-FIC-REPORT-FACTORY-DEV" in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "pull_request_target" not in text
    assert "id-token: write" not in text


def test_script_has_one_scoped_graph_mutation_and_no_secret_material() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"POST"' in text
    assert "federatedIdentityCredentials" in text
    assert '"PATCH"' not in text
    assert '"DELETE"' not in text
    assert "client_secret" not in text.casefold()
    assert "password" not in text.casefold()
    assert '"secret_value_exposed": False' in text
    assert '"identifiers_exposed": False' in text


def test_plan_path_does_not_call_mutation(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.platform, "node", lambda: "NOTERI")
    monkeypatch.setattr(MODULE, "_az", lambda: "az")
    monkeypatch.setattr(MODULE, "_tenant", lambda _az: MODULE.EXPECTED_TENANT)
    monkeypatch.setattr(MODULE, "_app_object_id", lambda _az: "object-id")
    monkeypatch.setattr(MODULE, "_list_fics", lambda _az, _object_id: [])

    result = MODULE.bootstrap(apply=False, confirm="")

    assert result["status"] == "planned"
    assert result["created"] is False
    assert result["mutation_performed"] is False


def test_existing_exact_fic_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.platform, "node", lambda: "NOTERI")
    monkeypatch.setattr(MODULE, "_az", lambda: "az")
    monkeypatch.setattr(MODULE, "_tenant", lambda _az: MODULE.EXPECTED_TENANT)
    monkeypatch.setattr(MODULE, "_app_object_id", lambda _az: "object-id")
    monkeypatch.setattr(
        MODULE,
        "_list_fics",
        lambda _az, _object_id: [
            {
                "name": MODULE.CREDENTIAL_NAME,
                "issuer": MODULE.ISSUER,
                "subject": MODULE.SUBJECT,
                "audiences": [MODULE.AUDIENCE],
            }
        ],
    )

    result = MODULE.bootstrap(apply=True, confirm=MODULE.CONFIRMATION)

    assert result["status"] == "ready"
    assert result["created"] is False
    assert result["mutation_performed"] is False
