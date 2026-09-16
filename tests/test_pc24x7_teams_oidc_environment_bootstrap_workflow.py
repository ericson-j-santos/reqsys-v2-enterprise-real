from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml')


def test_workflow_usa_oidc_main_sem_environment() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: development' not in text
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'CCP_AZURE_TENANT_ID: ${{ vars.CCP_AZURE_TENANT_ID }}' in text
    assert 'CCP_AZURE_SUBSCRIPTION_ID: ${{ vars.CCP_AZURE_SUBSCRIPTION_ID }}' in text
    assert 'id-token: write' in text


def test_workflow_cria_somente_fic_dev_sem_escalada() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'bootstrap_pc24x7_teams_oidc_environment.py' in text
    assert 'CRIAR-FIC-PC24X7-TEAMS-DEV' in text
    assert 'Application.ReadWrite.All' not in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-app.fly.dev' not in text
