"""Testes do canal 'flow_bot' (Power Automate Chat with Flow bot) do Teams Messaging Gateway."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services import teams_gateway as svc


def _run(coro):
    return asyncio.run(coro)


def _configurar_flow_bot(monkeypatch, configurado: bool = True) -> None:
    monkeypatch.setattr(
        svc.settings, 'teams_flow_bot_webhook_url', 'https://prod-00.brazilsouth.logic.azure.com/flow' if configurado else ''
    )


def test_payload_flow_bot_usa_schema_real_validado_em_producao():
    payload = svc._payload_flow_bot(
        'fulano@tieri659.onmicrosoft.com', 'Corpo da mensagem', {'titulo': 'Alerta'}, 'corr-payload-1'
    )

    assert payload == {
        'to': 'fulano@tieri659.onmicrosoft.com',
        'title': 'Alerta',
        'content': 'Corpo da mensagem',
        'signature': 'ReqSys',
        'correlationId': 'corr-payload-1',
    }


def test_status_gateway_flow_bot_reflete_configuracao_real(monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=False)

    status = svc.status_gateway()

    rota = next(r for r in status['rotas'] if r['canal'] == 'flow_bot')
    assert rota['disponivel'] is False
    assert any('TEAMS_FLOW_BOT_WEBHOOK_URL' in campo for campo in rota['campos_faltantes'])

    _configurar_flow_bot(monkeypatch, configurado=True)
    status = svc.status_gateway()
    rota = next(r for r in status['rotas'] if r['canal'] == 'flow_bot')
    assert rota['disponivel'] is True
    assert rota['campos_faltantes'] == []


def test_deve_usar_flow_bot_modo_explicito_mesmo_sem_configuracao(monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=False)
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat', destino_id='fulano@tieri659.onmicrosoft.com', texto='Ola', modo='flow_bot'
    )

    assert svc._deve_usar_flow_bot(payload) is True


def test_deve_usar_flow_bot_auto_quando_bot_nao_configurado(monkeypatch):
    monkeypatch.setattr(svc.settings, 'teams_bot_app_id', '')
    monkeypatch.setattr(svc.settings, 'teams_bot_app_tenant_id', '')
    monkeypatch.setattr(svc.settings, 'teams_bot_secret', '')
    _configurar_flow_bot(monkeypatch, configurado=True)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='fulano@tieri659.onmicrosoft.com', texto='Ola')

    assert svc._deve_usar_flow_bot(payload) is True


def test_deve_usar_flow_bot_auto_falso_quando_bot_configurado(monkeypatch):
    monkeypatch.setattr(svc.settings, 'teams_bot_app_id', 'bot-app-id')
    monkeypatch.setattr(svc.settings, 'teams_bot_app_tenant_id', 'bot-tenant-id')
    monkeypatch.setattr(svc.settings, 'teams_bot_secret', 'bot-secret')
    _configurar_flow_bot(monkeypatch, configurado=True)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='fulano@tieri659.onmicrosoft.com', texto='Ola')

    assert svc._deve_usar_flow_bot(payload) is False


def test_enviar_gateway_flow_bot_nao_configurado_retorna_erro_claro(monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=False)
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat', destino_id='fulano@tieri659.onmicrosoft.com', texto='Ola', modo='flow_bot'
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-fb-1'))

    assert resultado['entregue'] is False
    assert resultado['canal_usado'] == 'flow_bot'
    assert 'TEAMS_FLOW_BOT_WEBHOOK_URL' in resultado['erro']


def test_enviar_gateway_flow_bot_sem_destino_id_retorna_erro_claro(monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=True)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', texto='Ola', modo='flow_bot')

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-fb-2'))

    assert resultado['entregue'] is False
    assert resultado['canal_usado'] == 'flow_bot'
    assert 'destino_id' in resultado['erro']


@patch('app.services.teams_gateway._enviar_flow_bot_webhook', new_callable=AsyncMock)
def test_enviar_gateway_flow_bot_sucesso(mock_enviar, monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=True)
    mock_enviar.return_value = {'status_code': 202}
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='fulano@tieri659.onmicrosoft.com',
        texto='Ola via flow bot',
        modo='flow_bot',
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-fb-3'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'flow_bot'
    assert resultado['status_code'] == 202
    mock_enviar.assert_awaited_once()
    args = mock_enviar.await_args.args
    assert args[1] == 'fulano@tieri659.onmicrosoft.com'
    assert args[2] == 'Ola via flow bot'


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
@patch('app.services.teams_gateway._enviar_flow_bot_webhook', new_callable=AsyncMock)
def test_enviar_gateway_flow_bot_fallback_para_webhook(mock_flow_bot, mock_webhook, monkeypatch):
    _configurar_flow_bot(monkeypatch, configurado=True)
    mock_flow_bot.side_effect = RuntimeError('falha simulada')
    mock_webhook.return_value = {'status_code': 200}
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='fulano@tieri659.onmicrosoft.com',
        texto='Fallback via flow bot',
        modo='flow_bot',
        webhook_url='https://example.invalid/webhook',
        permitir_fallback=True,
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-fb-4'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'webhook'
    assert resultado['fallback_usado'] is True
    mock_webhook.assert_awaited_once()
