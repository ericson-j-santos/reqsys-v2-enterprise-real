from pathlib import Path


WORKFLOW = Path('.github/workflows/pc24x7-teams-token-bootstrap.yml')

NODE24_ACTIONS = {
    'actions/checkout': '3d3c42e5aac5ba805825da76410c181273ba90b1',
    'actions/setup-python': '5fda3b95a4ea91299a34e894583c3862153e4b97',
    'actions/upload-artifact': '043fb46d1a93c77aae656e7c1c64a875d1fc6a0a',
    'azure/login': 'a641126d1b8aa4d1fa005f4f92df94a3a4c4c906',
}


def test_workflow_usa_actions_node24_fixadas_por_sha() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    for action, sha in NODE24_ACTIONS.items():
        assert f'{action}@{sha}' in text
    assert 'Node 24' in text
    assert '11d5960a326750d5838078e36cf38b85af677262' not in text
    assert 'a26af69be951a213d495a4c3e4e4022e16d87065' not in text
    assert 'ea165f8d65b6e75b540449e92b4886f43607fa02' not in text
    assert '7184910d9eb2b1c5e48f7073824a90609bb9b6d6' not in text


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
    assert 'New-Item -ItemType Directory -Force -Path artifacts/pc24x7-teams-runtime-reconcile' in text
    assert '--output artifacts/pc24x7-teams-runtime-reconcile/signed-locator.json' in text
    assert 'steps.locator_bootstrap.outputs.base_url' in text
    assert 'reqsys-pc24x7-teams-service-token' in text

def test_bootstrap_bloqueia_runtime_defasado_antes_de_oidc_e_mutacao() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile = text.split('  reconcile-runtime-dev:', 1)[1].split('\n  bootstrap-token-dev:', 1)[0]
    bootstrap = text.split('  bootstrap-token-dev:', 1)[1].split('\n  bootstrap-dev:', 1)[0]
    oidc = reconcile.index('Login Azure por OIDC para reconciliar runtime DEV')
    runtime = reconcile.index('Reconciliar runtime PC24x7 DEV no SHA do workflow')
    mutation = bootstrap.index('Validar ou provisionar token S2S no PC24x7')
    assert oidc < runtime
    assert mutation >= 0
    assert '--expected-sha "${{ github.sha }}"' in reconcile
    assert 'resolve_pc24x7_dev_locator.mjs --output' in bootstrap



def test_bootstrap_autocorrige_runtime_pc24x7_antes_do_token() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile_job = text.index('  reconcile-runtime-dev:')
    token_job = text.index('  bootstrap-token-dev:')
    bootstrap_job = text.index('  bootstrap-dev:')
    assert reconcile_job < token_job < bootstrap_job
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in text
    assert 'needs: [contract, reconcile-runtime-dev]' in text
    assert 'needs: [contract, reconcile-runtime-dev, bootstrap-token-dev]' in text
    assert 'reconcile_pc24x7_teams_dev_runtime.py' in text
    assert '--confirm RECONCILE-PC24X7-TEAMS-DEV' in text
    assert '--expected-sha "${{ github.sha }}"' in text
    assert 'Publicar evidência sanitizada da reconciliação' in text


def test_bootstrap_script_prefere_cofre_local_quando_admin_jwt_nao_e_injetado() -> None:
    script = Path('scripts/bootstrap_pc24x7_teams_service_token.py').read_text(encoding='utf-8')
    assert 'mint_service_token_from_local_runtime(local_cofre_container' in script
    assert 'read_admin_jwt' not in script
    assert 'human_admin_jwt' not in script
    assert 'COFRE_ADMIN_JWT' not in script


def test_bootstrap_local_nao_fabrica_identidade_humana() -> None:
    script = Path('scripts/bootstrap_pc24x7_teams_service_token.py').read_text(encoding='utf-8')
    assert 'app.core.dev_service_token_bootstrap' in script
    assert "criar_token({'sub':'pc24x7-bootstrap','papel':'admin'}" not in script
    assert 'http://127.0.0.1:8000/api/v1/admin/service-tokens' not in script


def test_mint_roda_no_mesmo_job_self_hosted_que_le_o_cofre_local() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile = text.split('  reconcile-runtime-dev:', 1)[1].split('\n  bootstrap-token-dev:', 1)[0]
    token_job = text.split('  bootstrap-token-dev:', 1)[1].split('\n  bootstrap-dev:', 1)[0]
    bootstrap = text.split('  bootstrap-dev:', 1)[1]
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in reconcile
    assert 'Validar ou provisionar token S2S no PC24x7' not in reconcile
    assert "GetEnvironmentVariable('VAULT_API_TOKEN')" not in reconcile
    assert 'runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]' in token_job
    assert 'PC24X7_LOCAL_COFRE_CONTAINER: wt-pc24x7-piloto-api-1' in token_job
    assert "GetEnvironmentVariable('VAULT_API_TOKEN')" not in token_job
    assert 'Validar ou provisionar token S2S no PC24x7' in token_job
    assert 'bootstrap_pc24x7_teams_service_token.py' in token_job
    assert 'COFRE_ADMIN_JWT' not in token_job
    assert 'VAULT_API_TOKEN' not in bootstrap
    assert 'COFRE_ADMIN_JWT' not in bootstrap
    assert 'PC24x7_BOOTSTRAP_READY=true' in bootstrap


def test_reconcile_publica_evidencia_antes_do_bootstrap_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    reconcile = text.split('  reconcile-runtime-dev:', 1)[1].split('\n  bootstrap-token-dev:', 1)[0]
    token_job = text.split('  bootstrap-token-dev:', 1)[1].split('\n  bootstrap-dev:', 1)[0]
    assert 'Publicar evidência sanitizada da reconciliação' in reconcile
    assert 'if: always()' in reconcile
    assert 'VAULT_API_TOKEN_missing_on_pc24x7' not in reconcile
    assert 'needs: [contract, reconcile-runtime-dev]' in token_job
    assert 'VAULT_API_TOKEN_missing_on_pc24x7' not in token_job

