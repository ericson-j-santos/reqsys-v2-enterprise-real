from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml')


def test_workflow_main_oidc_sem_environment() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: development' not in text
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'id-token: write' in text


def test_workflow_nao_escalona_permissao() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'Application.ReadWrite.All' not in text
    assert 'bootstrap_pc24x7_teams_oidc_environment.py' in text
    assert 'CRIAR-FIC-PC24X7-TEAMS-DEV' in text
