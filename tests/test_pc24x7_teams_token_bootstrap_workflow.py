from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-token-bootstrap.yml')


def test_bootstrap_usa_jwt_admin_e_identidade_mutadora() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: development' in text
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'CCP_AZURE_CLIENT_ID_DEV' not in text
    assert 'COFRE_ADMIN_JWT: ${{ secrets.COFRE_ADMIN_JWT }}' in text
    assert 'VAULT_API_TOKEN: ${{ secrets.VAULT_API_TOKEN }}' not in text
    assert 'COFRE_API_URL: ${{ secrets.COFRE_API_URL }}' not in text
    assert "PC24X7_TEAMS_ALLOW_PROVISION: 'true'" in text


def test_bootstrap_permanece_dev_only() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'https://reqsys-api-dev.fly.dev' in text
    assert 'reqsys-pc24x7-teams-service-token' in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-app.fly.dev' not in text
