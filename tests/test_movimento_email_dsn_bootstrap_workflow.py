from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "movimento-email-dsn-bootstrap.yml"
)


def test_movimento_email_dsn_bootstrap_uses_governed_oidc_identity() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "vars.CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND" in workflow
    assert "vars.CCP_AZURE_TENANT_ID" in workflow
    assert "vars.CCP_AZURE_SUBSCRIPTION_ID" in workflow

    assert "vars.AZURE_CLIENT_ID" not in workflow
    assert "vars.AZURE_TENANT_ID" not in workflow
    assert "vars.AZURE_SUBSCRIPTION_ID" not in workflow

    assert "id-token: write" in workflow
    assert "uses: azure/login@v2" in workflow
    assert "client-secret:" not in workflow

    bootstrap = workflow.split("  bootstrap:\n", 1)[1]
    assert "environment: development" in bootstrap
    assert bootstrap.index("environment: development") < bootstrap.index("- name: Login Azure por OIDC")
    assert "vars.MOVIMENTO_EMAIL_SQL_USERNAME_SECRET || 'movimento-email-sql-username'" in bootstrap
    assert "vars.MOVIMENTO_EMAIL_SQL_PASSWORD_SECRET || 'movimento-email-sql-password'" in bootstrap


def test_movimento_email_dsn_bootstrap_fails_closed_before_azure_login() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    validation = workflow.index("- name: Validar configuração OIDC governada")
    login = workflow.index("- name: Login Azure por OIDC")
    assert validation < login

    for required_name in (
        "AZURE_CLIENT_ID",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "REQSYS_KEY_VAULT_NAME",
    ):
        assert required_name in workflow

    assert 'echo "::error::$name não configurado; bootstrap permanece fail-closed."' in workflow
    assert "exit 2" in workflow
