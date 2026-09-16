from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_workflow_permanece_dev_only_e_sem_environment() -> None:
    text = _text()
    assert 'environment: development' not in text
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'CCP_AZURE_TENANT_ID: ${{ vars.CCP_AZURE_TENANT_ID }}' in text
    assert 'CCP_AZURE_SUBSCRIPTION_ID: ${{ vars.CCP_AZURE_SUBSCRIPTION_ID }}' in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-app.fly.dev' not in text


def test_workflow_cria_somente_fic_environment_development() -> None:
    text = _text()
    assert 'bootstrap_pc24x7_teams_oidc_environment.py' in text
    assert 'CRIAR-FIC-PC24X7-TEAMS-DEV' in text
    assert 'Application.ReadWrite.All' not in text
    assert 'id-token: write' in text
