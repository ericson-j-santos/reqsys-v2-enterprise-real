from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "governance" / "human_action_workflow.py"
SPEC = importlib.util.spec_from_file_location("human_action_workflow", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _valid_p01_evidence() -> dict:
    return {
        "action_id": "P0-1",
        "status": "evidence_received",
        "evidence": {
            "app_registration_id": "app-registration-reference",
            "vault_secret_reference": "kv://reqsys-dev/teams-bot-client-secret",
            "bootstrap_run_id": "run-123",
            "teams_installation_evidence": "teams-install-123",
            "e2e_correlation_id": "corr-123",
            "bootstrap_blocker": "NONE",
            "bot_provisioned": True,
            "teams_package_installed": True,
            "bidirectional_conversation_verified": True,
        },
    }


def test_catalog_has_all_consolidated_human_actions() -> None:
    catalog = module.load_catalog()
    ids = {item["id"] for item in catalog["items"]}

    assert len(ids) == 15
    assert ids == {
        "P0-1", "P0-2", "P0-3", "P0-4", "P0-5", "P0-6", "P0-7", "P0-8",
        "P1-1", "P1-2", "P1-3", "P1-4", "P1-5", "P2-1", "P2-2",
    }


def test_p01_valid_evidence_closes_gate() -> None:
    catalog = module.load_catalog()
    action = module.find_action(catalog, "P0-1")

    result = module.validate_evidence(action, _valid_p01_evidence())

    assert result.valid is True
    assert result.status == "validated"
    assert result.errors == []
    assert result.missing_evidence == []


def test_p01_keeps_gate_closed_while_bootstrap_blocker_exists() -> None:
    catalog = module.load_catalog()
    action = module.find_action(catalog, "P0-1")
    evidence = _valid_p01_evidence()
    evidence["evidence"]["bootstrap_blocker"] = "TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED"

    result = module.validate_evidence(action, evidence)

    assert result.valid is False
    assert result.status == "validation_failed"
    assert any("TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED" in error for error in result.errors)


def test_missing_or_secret_like_value_is_not_accepted_as_evidence() -> None:
    catalog = module.load_catalog()
    action = module.find_action(catalog, "P0-1")
    evidence = _valid_p01_evidence()
    evidence["evidence"]["vault_secret_reference"] = "secret"

    result = module.validate_evidence(action, evidence)

    assert result.valid is False
    assert "vault_secret_reference" in result.missing_evidence


def test_blueprint_exposes_owner_actions_evidence_and_verification() -> None:
    catalog = module.load_catalog()
    action = module.find_action(catalog, "P0-1")

    blueprint = module.render_blueprint(action)

    assert "Blueprint humano — P0-1" in blueprint
    assert "entra_teams_admin" in blueprint
    assert "vault_secret_reference" in blueprint
    assert "TEAMS_BOT_IDENTITY_BOOTSTRAP_REQUIRED" in blueprint
    assert "ReqSys → IA → Teams → mesma conversa" in blueprint
