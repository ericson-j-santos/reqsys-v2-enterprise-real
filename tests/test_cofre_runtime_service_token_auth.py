from pathlib import Path

CONTROL = Path("scripts/cofre_remote_runtime_control.py")
BOOTSTRAP = Path("scripts/bootstrap_pc24x7_teams_service_token.py")
WORKFLOW = Path(".github/workflows/cofre-runtime-evidence-gate.yml")


def test_cofre_control_prefers_scoped_service_token() -> None:
    raw = CONTROL.read_text(encoding="utf-8")
    assert '"X-Service-Token"' in raw
    assert 'COFRE_RUNTIME_SERVICE_TOKEN' in raw
    assert 'elif self.admin_jwt:' in raw


def test_service_token_bootstrap_is_scope_parameterized() -> None:
    raw = BOOTSTRAP.read_text(encoding="utf-8")
    assert "REQSYS_SERVICE_TOKEN_SCOPE" in raw
    assert "REQSYS_SERVICE_TOKEN_LABEL" in raw
    assert "REQSYS_SERVICE_TOKEN_SECRET_NAME" in raw
    assert "REQSYS_SERVICE_TOKEN_VALIDATION_PATH" in raw


def test_cofre_gate_no_longer_uses_expiring_admin_jwt() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "COFRE_RUNTIME_SERVICE_TOKEN" in raw
    assert "COFRE_ADMIN_JWT" not in raw
    assert "id-token: write" in raw
    assert "azure/login@7184910d9eb2b1c5e48f7073824a90609bb9b6d6" in raw
    assert 'az keyvault secret show --vault-name "$REQSYS_KEY_VAULT_NAME"' in raw
    assert "secrets.COFRE_RUNTIME_SERVICE_TOKEN" not in raw
