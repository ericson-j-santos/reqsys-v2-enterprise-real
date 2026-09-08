from pathlib import Path


WORKFLOW = Path('.github/workflows/teams-bot-dev-provision.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_provisionamento_real_nunca_roda_em_pull_request() -> None:
    text = _text()
    assert "github.event_name != 'pull_request'" in text
    assert "vars.CCP_ENABLED == 'true'" in text


def test_escopo_e_exclusivamente_dev() -> None:
    text = _text()
    assert 'FLY_APP: reqsys-api-dev' in text
    assert 'reqsys-api-stg' not in text
    assert 'reqsys-api\n' not in text
    assert 'APROVO-PROD' not in text
    assert 'production' not in text.lower()


def test_bot_e_single_tenant_f0_com_endpoint_exato() -> None:
    text = _text()
    assert '--app-type SingleTenant' in text
    assert '--sku F0' in text
    assert (
        'TARGET_ENDPOINT: https://reqsys-api-dev.fly.dev/v1/teams-gateway/'
        'ai-conversations/bot/messages'
    ) in text
    assert 'az bot msteams create' in text


def test_identidade_e_secret_nao_sao_persistidos_no_repositorio() -> None:
    text = _text()
    assert 'az ad app credential reset' in text
    assert '::add-mask::$CLIENT_SECRET' in text
    assert 'TEAMS_BOT_SECRET=$CLIENT_SECRET' in text
    assert 'secret_value_exposed' in text
    assert "'secret_value_exposed': False" in text
    assert 'CLIENT_SECRET=' not in text.replace('CLIENT_SECRET=""', '').replace('CLIENT_SECRET="$(' ,'')


def test_fly_token_vem_do_credential_control_plane() -> None:
    text = _text()
    assert 'uses: ./.github/actions/resolve-managed-credential' in text
    assert 'credential-id: fly-api-dev-deploy' in text
    assert 'consumer: github-actions:fly-dev' in text
    assert 'export-env: FLY_API_TOKEN' in text


def test_preflight_acontece_antes_das_mutacoes_azure() -> None:
    text = _text()
    preflight = text.index('flyctl status --app "$FLY_APP"')
    create_app = text.index('az ad app create')
    create_bot = text.index('az bot create')
    set_secrets = text.index('flyctl secrets set')
    assert preflight < create_app < create_bot < set_secrets


def test_rollback_so_remove_recursos_criados_pela_execucao() -> None:
    text = _text()
    assert 'CREATED_APP=0' in text
    assert 'CREATED_SP=0' in text
    assert 'CREATED_GROUP=0' in text
    assert 'CREATED_BOT=0' in text
    assert 'if [ "$CREATED_BOT" -eq 1 ]' in text
    assert 'if [ "$CREATED_SP" -eq 1 ]' in text
    assert 'if [ "$CREATED_APP" -eq 1 ]' in text
    assert 'if [ "$CREATED_GROUP" -eq 1 ]' in text


def test_nao_reutiliza_app_registration_existente_implicitamente() -> None:
    text = _text()
    assert 'az ad app list --display-name "$APP_DISPLAY_NAME"' in text
    assert 'if [ "$existing_apps" != "0" ]' in text
    assert 'Nenhuma identidade existente será reutilizada implicitamente.' in text


def test_pacote_teams_usa_app_id_real_e_bot_conversacional() -> None:
    text = _text()
    assert 'APP_ID_FOR_PACKAGE="$APP_ID" python' in text
    assert "manifest['id'] = app_id" in text
    assert "manifest['bots'][0]['botId'] = app_id" in text
    assert "manifest['bots'][0]['isNotificationOnly'] is False" in text
    assert 'audit/reqsys-teams-gateway-dev-v1.1.0.zip' in text


def test_segredos_runtime_sao_os_tres_exigidos_pela_1518() -> None:
    text = _text()
    for name in (
        'TEAMS_BOT_APP_ID',
        'TEAMS_BOT_APP_TENANT_ID',
        'TEAMS_BOT_SECRET',
    ):
        assert name in text
