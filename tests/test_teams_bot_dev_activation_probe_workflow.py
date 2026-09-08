from pathlib import Path

import yaml


WORKFLOW = Path('.github/workflows/teams-bot-dev-activation-probe.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def _workflow() -> dict:
    return yaml.safe_load(_text())


def test_sonda_usa_oidc_governado_e_subscription_existente() -> None:
    text = _text()
    assert 'azure/login@v2' in text
    assert 'CCP_AZURE_CLIENT_ID' in text
    assert 'CCP_AZURE_TENANT_ID' in text
    assert 'CCP_AZURE_SUBSCRIPTION_ID' in text
    assert 'id-token: write' in text


def test_sonda_e_somente_leitura() -> None:
    text = _text()
    forbidden = (
        'az bot update',
        'az resource update',
        'az bot msteams create',
        'az bot msteams delete',
        'az deployment group create',
    )
    assert all(command not in text for command in forbidden)
    assert "'mutation_executed': False" in text


def test_sonda_procura_bot_service_e_canal_teams_sem_segredos() -> None:
    text = _text()
    assert 'Microsoft.BotService/botServices' in text
    assert "'az', 'bot', 'show'" in text
    assert "'az', 'bot', 'msteams', 'show'" in text
    assert "'--with-secrets', 'false'" in text
    assert 'TEAMS_BOT_SECRET' not in text


def test_endpoint_alvo_e_exatamente_o_dev_da_central_de_conversas() -> None:
    text = _text()
    assert (
        'https://reqsys-api-dev.fly.dev/v1/teams-gateway/'
        'ai-conversations/bot/messages'
    ) in text


def test_probe_real_nao_roda_em_pull_request() -> None:
    workflow = _workflow()
    job = workflow['jobs']['azure-probe']
    assert "github.event_name != 'pull_request'" in job['if']


def test_push_em_main_dispara_sonda_quando_workflow_e_integrado() -> None:
    text = _text()
    assert 'push:' in text
    assert 'branches: [main]' in text
    assert '.github/workflows/teams-bot-dev-activation-probe.yml' in text
