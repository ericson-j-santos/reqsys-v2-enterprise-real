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


def test_bootstrap_permanece_dev_only_e_resolve_locator_assinado() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'https://reqsys-api-dev.fly.dev' not in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-app.fly.dev' not in text
    assert 'resolve_pc24x7_dev_locator.mjs --self-test' in text
    assert '--output artifacts/pc24x7-teams-token/signed-locator.json' in text
    assert 'steps.locator.outputs.api_base_url' in text
    assert "printf 'REQSYS_API_BASE_URL=%s\\n' \"$RESOLVED_API_BASE\" >> \"$GITHUB_ENV\"" in text
    assert 'reqsys-pc24x7-teams-service-token' in text
    assert 'signed-locator.json' in text
