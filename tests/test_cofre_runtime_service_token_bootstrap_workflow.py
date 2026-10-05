from pathlib import Path

WORKFLOW = Path(".github/workflows/cofre-runtime-service-token-bootstrap.yml")


def test_cofre_bootstrap_uses_least_privilege_scope_and_dedicated_secret() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "REQSYS_SERVICE_TOKEN_SCOPE: cofre:runtime_evidence" in raw
    assert "REQSYS_SERVICE_TOKEN_LABEL: cofre-runtime-evidence-dev" in raw
    assert "reqsys-cofre-runtime-evidence-service-token" in raw
    assert "REQSYS_SERVICE_TOKEN_VALIDATION_PATH: /v1/cofre/runtime/control-status" in raw


def test_cofre_bootstrap_never_uses_github_admin_jwt() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "COFRE_ADMIN_JWT" not in raw
    assert "VAULT_API_TOKEN" in raw
    assert "::add-mask::$vaultToken" in raw


def test_cofre_bootstrap_pins_external_actions() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in raw
    assert "azure/login@7184910d9eb2b1c5e48f7073824a90609bb9b6d6" in raw
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in raw
