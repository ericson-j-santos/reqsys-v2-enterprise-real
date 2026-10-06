from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-token-bootstrap.yml')


def test_bootstrap_nao_injeta_jwt_admin_do_github() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'environment: development' in text
    assert 'CCP_AZURE_CLIENT_ID: ${{ vars.CCP_AZURE_CLIENT_ID }}' in text
    assert 'CCP_AZURE_CLIENT_ID_DEV' not in text
    assert 'COFRE_ADMIN_JWT: ${{ secrets.COFRE_ADMIN_JWT }}' not in text
    assert 'VAULT_API_TOKEN: ${{ secrets.VAULT_API_TOKEN }}' not in text
    assert 'COFRE_API_URL: ${{ secrets.COFRE_API_URL }}' not in text
    assert "PC24X7_TEAMS_ALLOW_PROVISION: 'true'" in text


def test_bootstrap_permanece_dev_only_e_resolve_locator_assinado() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'https://reqsys-api-dev.fly.dev' not in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-app.fly.dev' not in text
    assert '--output artifacts/pc24x7-teams-runtime-reconcile/signed-locator.json' in text
    assert 'steps.locator_bootstrap.outputs.base_url' in text
    assert 'reqsys-pc24x7-teams-service-token' in text

def test_bootstrap_bloqueia_runtime_defasado_antes_de_oidc_e_mutacao() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile = text.split('  reconcile-runtime-dev:', 1)[1].split('\n  bootstrap-dev:', 1)[0]
    oidc = reconcile.index('Login Azure por OIDC para reconciliar runtime DEV')
    runtime = reconcile.index('Reconciliar runtime PC24x7 DEV no SHA do workflow')
    mutation = reconcile.index('Validar ou provisionar token S2S no PC24x7')
    assert oidc < runtime < mutation
    assert '--expected-sha "${{ github.sha }}"' in reconcile
    assert 'resolve_pc24x7_dev_locator.mjs --output' in reconcile



def test_bootstrap_autocorrige_runtime_pc24x7_antes_do_token() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile_job = text.index('  reconcile-runtime-dev:')
    bootstrap_job = text.index('  bootstrap-dev:')
    assert reconcile_job < bootstrap_job
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in text
    assert 'needs: [contract, reconcile-runtime-dev]' in text
    assert 'reconcile_pc24x7_teams_dev_runtime.py' in text
    assert '--confirm RECONCILE-PC24X7-TEAMS-DEV' in text
    assert '--expected-sha "${{ github.sha }}"' in text
    assert 'Publicar evidência sanitizada da reconciliação' in text


def test_bootstrap_script_prefere_cofre_local_quando_admin_jwt_nao_e_injetado() -> None:
    script = Path('scripts/bootstrap_pc24x7_teams_service_token.py').read_text(encoding='utf-8')
    assert 'read_admin_jwt_from_local_runtime(local_cofre_container' in script
    assert "read_admin_jwt(cofre_base, vault_token, environment='dev')" in script
    assert "/v1/cofre/segredos/human_admin_jwt:{environment}" in script
    assert "admin_jwt_expired_or_too_close_to_expiry" in script


def test_mint_roda_no_mesmo_job_self_hosted_que_le_o_cofre_local() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile = text.split('  reconcile-runtime-dev:', 1)[1].split('\n  bootstrap-dev:', 1)[0]
    bootstrap = text.split('  bootstrap-dev:', 1)[1]
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in reconcile
    assert 'PC24X7_LOCAL_COFRE_CONTAINER: wt-pc24x7-piloto-api-1' in reconcile
    assert "GetEnvironmentVariable('VAULT_API_TOKEN')" not in reconcile
    assert 'Validar ou provisionar token S2S no PC24x7' in reconcile
    assert 'bootstrap_pc24x7_teams_service_token.py' in reconcile
    assert 'COFRE_ADMIN_JWT' not in reconcile
    assert 'VAULT_API_TOKEN' not in bootstrap
    assert 'COFRE_ADMIN_JWT' not in bootstrap
    assert 'PC24x7_BOOTSTRAP_READY=true' in bootstrap

