from pathlib import Path


WORKFLOW = Path('.github/workflows/key-vault-rbac-bootstrap-dev.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_bootstrap_so_executa_na_main_e_no_cofre_dev() -> None:
    text = _text()
    assert "branches: [main]" in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "TARGET_VAULT_NAME: kv-reqsys-ccp" in text
    assert "TARGET_RESOURCE_GROUP: rg-reqsys-ccp" in text
    assert "TARGET_PRINCIPAL_OID: 5660aef6-6eb0-43d1-889a-0af710fe9054" in text
    assert "TARGET_ROLE_ID: 4633458b-17de-408a-b874-0445c86b69e6" in text


def test_grant_usa_identidade_mutadora_sem_environment() -> None:
    text = _text()
    grant = text.split("  grant:\n", 1)[1].split("  verify-reader-and-dispatch:\n", 1)[0]
    assert "CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}" in grant
    assert "environment:" not in grant
    assert "--assignee-object-id \"$TARGET_PRINCIPAL_OID\"" in grant
    assert "--assignee-principal-type ServicePrincipal" in grant
    assert "--scope \"$scope\"" in grant


def test_bootstrap_nao_le_valores_de_segredos() -> None:
    text = _text()
    assert "az keyvault secret show" not in text
    assert "secret_values_read\":false" in text
    assert "production_touched\":false" in text
    assert "test_touched\":false" in text


def test_reader_dev_so_prova_metadata_e_dispara_captura_estrita() -> None:
    text = _text()
    verify = text.split("  verify-reader-and-dispatch:\n", 1)[1]
    assert "environment: development" in verify
    assert "CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND" in verify
    assert "az keyvault secret list" in verify
    assert "--maxresults 1" in verify
    assert "integration-excel-sql-sharepoint-key-vault-capture-dev.yml" in verify
    assert "-f strict=true" in verify


def test_gate_falha_fechado_sem_atribuicao_observada() -> None:
    text = _text()
    assert "role_assignment_not_observed_after_write" in text
    assert "key_vault_rbac_bootstrap_not_resolved" in text
    assert "role_assignment_verified') is not True" in text
