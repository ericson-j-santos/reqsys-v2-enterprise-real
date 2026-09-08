from pathlib import Path

import yaml


WORKFLOW = Path('.github/workflows/teams-bot-dev-provision.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def _workflow() -> dict:
    return yaml.safe_load(_text())


def test_jobs_reais_nunca_rodam_em_pull_request() -> None:
    workflow = _workflow()
    for name in ('provision-azure', 'configure-runtime-dev'):
        condition = workflow['jobs'][name]['if']
        assert "github.event_name != 'pull_request'" in condition
        assert "vars.CCP_ENABLED == 'true'" in condition


def test_identidade_mutadora_fica_fora_de_environment_dev() -> None:
    workflow = _workflow()
    job = workflow['jobs']['provision-azure']
    assert 'environment' not in job
    text = _text()
    assert 'client-id: ${{ env.CCP_AZURE_CLIENT_ID }}' in text


def test_reader_fly_usa_environment_dev_e_identidade_dev() -> None:
    workflow = _workflow()
    job = workflow['jobs']['configure-runtime-dev']
    assert job['environment'] == 'dev'
    text = _text()
    assert 'CCP_AZURE_CLIENT_ID_DEV: ${{ vars.CCP_AZURE_CLIENT_ID_DEV }}' in text
    assert 'azure-client-id: ${{ env.CCP_AZURE_CLIENT_ID_DEV }}' in text


def test_fly_token_vem_do_credential_control_plane() -> None:
    text = _text()
    assert 'uses: ./.github/actions/resolve-managed-credential' in text
    assert 'credential-id: fly-api-dev-deploy' in text
    assert 'consumer: github-actions:fly-dev' in text
    assert 'export-env: FLY_API_TOKEN' in text


def test_bot_e_single_tenant_f0_com_endpoint_exato() -> None:
    text = _text()
    assert '--app-type SingleTenant' in text
    assert '--sku F0' in text
    assert (
        'TARGET_ENDPOINT: https://reqsys-api-dev.fly.dev/v1/teams-gateway/'
        'ai-conversations/bot/messages'
    ) in text
    assert 'az bot msteams create' in text


def test_secret_do_bot_fica_no_keyvault_entre_os_jobs() -> None:
    text = _text()
    assert 'BOT_SECRET_VAULT_NAME: reqsys-teams-bot-dev-secret' in text
    assert 'az keyvault secret set' in text
    assert 'az keyvault secret show' in text
    assert '--value "$CLIENT_SECRET"' in text
    assert '::add-mask::$CLIENT_SECRET' in text
    assert '::add-mask::$BOT_SECRET' in text


def test_nenhum_valor_secreto_e_job_output() -> None:
    text = _text()
    assert 'echo "app_id=$APP_ID" >> "$GITHUB_OUTPUT"' in text
    assert 'CLIENT_SECRET' not in ''.join(
        line for line in text.splitlines() if 'GITHUB_OUTPUT' in line
    )
    assert 'BOT_SECRET' not in ''.join(
        line for line in text.splitlines() if 'GITHUB_OUTPUT' in line
    )


def test_rollback_azure_so_antes_do_commit_no_keyvault() -> None:
    text = _text()
    assert 'COMMITTED=0' in text
    assert 'if [ "$rc" -ne 0 ] && [ "$COMMITTED" -eq 0 ]' in text
    assert 'CREATED_APP=0' in text
    assert 'CREATED_SP=0' in text
    assert 'CREATED_GROUP=0' in text
    assert 'CREATED_BOT=0' in text
    assert 'COMMITTED=1' in text
    assert text.index('az keyvault secret set') < text.index('COMMITTED=1')


def test_nao_reutiliza_bot_ou_app_existente_implicitamente() -> None:
    text = _text()
    assert 'Microsoft.BotService/botServices' in text
    assert 'if [ "$existing_bots" != "0" ]' in text
    assert 'az ad app list --display-name "$APP_DISPLAY_NAME"' in text
    assert 'if [ "$existing_apps" != "0" ]' in text


def test_pacote_teams_usa_app_id_real_e_bot_conversacional() -> None:
    text = _text()
    assert 'APP_ID_FOR_PACKAGE="$APP_ID" python' in text
    assert "manifest['id'] = app_id" in text
    assert "manifest['bots'][0]['botId'] = app_id" in text
    assert "manifest['bots'][0]['isNotificationOnly'] is False" in text
    assert 'audit/reqsys-teams-gateway-dev-v1.1.0.zip' in text


def test_runtime_configura_exatamente_os_tres_segredos_da_1518() -> None:
    text = _text()
    assert 'TEAMS_BOT_APP_ID=$BOT_APP_ID' in text
    assert 'TEAMS_BOT_APP_TENANT_ID=$CCP_AZURE_TENANT_ID' in text
    assert 'TEAMS_BOT_SECRET=$BOT_SECRET' in text


def test_runtime_valida_saude_dev_depois_dos_segredos() -> None:
    text = _text()
    set_secrets = text.index('flyctl secrets set')
    health = text.index('curl --fail --silent --show-error --retry 5')
    assert set_secrets < health
    assert 'HEALTH_URL: https://reqsys-api-dev.fly.dev/health' in text


def test_escopo_exclusivamente_dev() -> None:
    text = _text()
    assert 'FLY_APP: reqsys-api-dev' in text
    assert 'environment: dev' in text
    assert 'reqsys-api-stg' not in text
    assert 'APROVO-PROD' not in text
