from pathlib import Path

WORKFLOW = Path(".github/workflows/planner-teams-delegated-identity-bootstrap.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_bootstrap_is_manual_main_only_and_uses_oidc() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "id-token: write" in text
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in text
    assert "azure/login@v2" in text
    assert "client-secret:" not in text


def test_bootstrap_uses_minimum_delegated_identity_contract() -> None:
    text = _text()
    assert "bootstrap_planner_teams_delegated_identity.py" in text
    assert "CRIAR-IDENTIDADE-PLANNER-TEAMS-DEV" in text
    assert "bootstrap_pc24x7_teams_oidc_environment.py" in text
    assert "--environment reqsys-power-platform-dev" in text
    assert "reqsys-planner-teams-delegated-client-id-dev" in text
    assert "Application.ReadWrite.All" not in text
    assert "admin-consent" not in text.lower()
    assert "reqsys-api-stg" not in text
    assert "reqsys-api-prod" not in text


def test_bootstrap_publishes_only_sanitized_evidence() -> None:
    text = _text()
    assert "Revalidar somente metadados no Key Vault" in text
    assert "--query '{enabled:attributes.enabled,contentType:contentType,tags:tags}'" in text
    assert "actions/upload-artifact@v4" in text
