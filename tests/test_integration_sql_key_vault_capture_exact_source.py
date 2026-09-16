from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/integration-excel-sql-sharepoint-key-vault-capture-dev.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_usa_nome_exato_configurado_para_dsn_sql() -> None:
    text = _text()
    assert "INTEGRATION_E2E_SQL_DSN_SECRET_NAME: ${{ vars.INTEGRATION_E2E_SQL_DSN_SECRET_NAME }}" in text
    assert 'secret_name="${INTEGRATION_E2E_SQL_DSN_SECRET_NAME:-}"' in text
    assert 'az keyvault secret show --vault-name "$REQSYS_KEY_VAULT_NAME" --name "$secret_name"' in text
    assert '"selection_mode":"exact_configured_name"' in text


def test_nao_enumera_segredos_nem_aplica_heuristica_por_nome() -> None:
    text = _text()
    assert "az keyvault secret list" not in text
    assert "sql_candidate_count" not in text
    assert "candidate_count_mismatch" not in text
    assert "re.search" not in text


def test_falha_fechado_sem_nome_explicito_ou_com_nome_invalido() -> None:
    text = _text()
    assert '"status":"secret_name_unconfigured"' in text
    assert '"status":"secret_name_invalid"' in text
    assert "^[A-Za-z0-9-]{1,127}$" in text
    assert '"secret_value_exposed":false' in text