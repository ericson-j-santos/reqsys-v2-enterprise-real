from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/integration-excel-sql-sharepoint-key-vault-capture-dev.yml"
)
PREFLIGHT = Path("scripts/integration_sql_capture_preflight.py")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _preflight() -> str:
    return PREFLIGHT.read_text(encoding="utf-8")


def test_usa_nome_exato_configurado_para_dsn_sql() -> None:
    workflow = _workflow()
    preflight = _preflight()
    assert "INTEGRATION_E2E_SQL_DSN_SECRET_NAME: ${{ vars.INTEGRATION_E2E_SQL_DSN_SECRET_NAME }}" in workflow
    assert 'secret_name="${INTEGRATION_E2E_SQL_DSN_SECRET_NAME:-}"' in workflow
    assert 'az keyvault secret show --vault-name "$REQSYS_KEY_VAULT_NAME" --name "$secret_name"' in workflow
    assert '"selection_mode": "exact_configured_name"' in preflight


def test_nao_enumera_segredos_nem_aplica_heuristica_por_nome() -> None:
    text = _workflow()
    assert "az keyvault secret list" not in text
    assert "sql_candidate_count" not in text
    assert "candidate_count_mismatch" not in text
    assert "re.search" not in text


def test_falha_fechado_sem_nome_explicito_ou_com_nome_invalido() -> None:
    text = _preflight()
    assert '"INTEGRATION_E2E_SQL_DSN_SECRET_NAME": bool(secret_name.strip())' in text
    assert '"oidc_configuration_missing"' in text
    assert '"oidc_configuration_invalid"' in text
    assert 'invalid.append("INTEGRATION_E2E_SQL_DSN_SECRET_NAME")' in text
    assert "[A-Za-z0-9-]{1,127}" in text
    assert '"secret_value_exposed": False' in text


def test_reader_nao_e_inferido_de_identidade_legada_ou_mutadora() -> None:
    workflow = _workflow()
    assert "--reader-configured false" in workflow
    assert "CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND" not in workflow
    assert "vars.CCP_AZURE_CLIENT_ID }}" not in workflow


def test_guard_do_cofre_dev_permanece_antes_de_login() -> None:
    workflow = _workflow()
    preflight = _preflight()
    assert '--expected-vault "$EXPECTED_KEY_VAULT_NAME"' in workflow
    assert '--actual-vault "$REQSYS_KEY_VAULT_NAME"' in workflow
    assert '"REQSYS_KEY_VAULT_TARGET_MATCH"' in preflight
