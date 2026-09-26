from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/teams-bot-dev-provision.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.safe_load(_text())


def _triggers() -> dict:
    workflow = _workflow()
    return workflow[True] if True in workflow else workflow["on"]


def test_workflow_is_identity_bootstrap_only() -> None:
    workflow = _workflow()
    triggers = _triggers()
    inputs = triggers["workflow_dispatch"]["inputs"]

    assert "schedule" not in triggers
    assert inputs["operation"]["options"] == ["identity-bootstrap"]
    assert inputs["operation"]["default"] == "identity-bootstrap"
    assert "force_runtime_sync" not in inputs
    assert "activate-dev" not in workflow["jobs"]
    assert "identity-bootstrap-dev" in workflow["jobs"]


def test_runtime_activation_is_owned_by_pc24x7_workflow() -> None:
    text = _text().lower()

    assert "reqsys-api-dev.fly.dev" not in text
    assert "flyctl" not in text
    assert "fly_api_token" not in text
    assert "fly_trust_anchor" not in text
    assert "superfly/" not in text


def test_identity_bootstrap_never_runs_implicitly() -> None:
    workflow = _workflow()
    condition = workflow["jobs"]["identity-bootstrap-dev"]["if"]

    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "inputs.operation == 'identity-bootstrap'" in condition


def test_identity_bootstrap_uses_noteri_and_governed_gateways() -> None:
    text = _text()

    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in text
    assert 'if ($env:COMPUTERNAME -ne "NOTERI")' in text
    assert "session_launcher.py" in text
    assert "SESSION_LAUNCH_OK" in text
    assert "owner_risk3_gateway.py" in text
    assert "ENABLE-TEAMS-BOT-DEV-IDENTITY-BOOTSTRAP-ONCE" in text
    assert "DISABLE-TEAMS-BOT-DEV-IDENTITY-BOOTSTRAP-ONCE" in text


def test_identity_bootstrap_preserves_dev_only_evidence_contract() -> None:
    text = _text()

    assert "CCP_AZURE_TENANT_ID: ${{ vars.CCP_AZURE_TENANT_ID }}" in text
    assert 'if ($data.environment -ne "dev")' in text
    assert 'if ($data.host -ne "NOTERI")' in text
    assert 'if ($data.independent_readback -ne $true)' in text
    assert 'if ($data.secret_value_exposed -ne $false)' in text
    assert 'if ($data.production_touched -ne $false)' in text
