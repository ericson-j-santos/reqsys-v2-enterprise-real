"""Testes do Teams Messaging Gateway."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services import teams_gateway as svc


def _run(coro):
    return asyncio.run(coro)


def test_status_gateway_explica_rotas(monkeypatch):
    monkeypatch.setattr(svc.settings, 'azure_tenant_id', 'tenant')
    monkeypatch.setattr(svc.settings, 'azure_client_id', 'client')
    monkeypatch.setattr(svc.settings, 'azure_client_secret', '')
    monkeypatch.setattr(svc.settings, 'teams_notifications_webhook_url', '')

    status = svc.status_gateway()

    assert status['schema_version'] == '1.0.0'
    rotas = {rota['canal']: rota for rota in status['rotas']}
    assert rotas['graph_delegado']['disponivel'] is True
    assert rotas['graph_delegado']['requer_usuario_logado'] is True
    assert rotas['webhook']['disponivel'] is False
    assert 'chat_humano_sem_usuario_logado' in status['politica']


def test_selecionar_rota_prefere_delegado_quando_ha_token():
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='chat-1',
        texto='Ola',
        usuario_access_token='token',
    )

    rota = svc.selecionar_rota(payload)

    assert rota['canal'] == 'graph_delegado'


@patch('app.services.teams_gateway.enviar_mensagem_chat_teams_como_usuario', new_callable=AsyncMock)
def test_enviar_gateway_auto_delegado(mock_enviar):
    mock_enviar.return_value = {
        'enviado': True,
        'message_id': 'msg-1',
        'chat_id': 'chat-1',
        'correlation_id': 'corr-1',
    }
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='chat-1',
        texto='Ola delegado',
        usuario_access_token='token',
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-1'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'graph_delegado'
    assert resultado['message_id'] == 'msg-1'
    mock_enviar.assert_awaited_once()


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
def test_enviar_gateway_webhook_configurado(mock_webhook):
    mock_webhook.return_value = {'status_code': 202}
    payload = TeamsGatewayMessageRequest(
        destino_tipo='canal',
        modo='webhook',
        webhook_url='https://example.invalid/webhook',
        texto='Alerta operacional',
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-2'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'webhook'
    assert resultado['status_code'] == 202
    mock_webhook.assert_awaited_once()


def test_enviar_gateway_chat_humano_sem_token_bloqueia_com_mensagem_clara():
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='chat-1', texto='Ola')

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-3'))

    assert resultado['entregue'] is False
    assert resultado['canal_usado'] is None
    assert 'usuario_access_token' in resultado['erro']
    assert resultado['motivo'] == 'sem_rota_segura'


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
@patch('app.services.teams_gateway.enviar_mensagem_chat_teams_como_usuario', new_callable=AsyncMock)
def test_enviar_gateway_fallback_delegado_para_webhook(mock_delegado, mock_webhook):
    mock_delegado.return_value = {'enviado': False, 'erro': 'HTTP 403: forbidden'}
    mock_webhook.return_value = {'status_code': 200}
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='chat-1',
        texto='Fallback',
        usuario_access_token='token',
        webhook_url='https://example.invalid/webhook',
        permitir_fallback=True,
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-4'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'webhook'
    assert resultado['fallback_usado'] is True
    mock_delegado.assert_awaited_once()
    mock_webhook.assert_awaited_once()


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
def test_enviar_gateway_dry_run_nao_chama_provider(mock_webhook):
    payload = TeamsGatewayMessageRequest(
        destino_tipo='canal',
        modo='webhook',
        webhook_url='https://example.invalid/webhook',
        texto='Planejar',
        dry_run=True,
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-5'))

    assert resultado['dry_run'] is True
    assert resultado['entregue'] is False
    assert resultado['canal_usado'] == 'webhook'
    assert resultado['motivo'] == 'dry_run: mensagem nao enviada'
    mock_webhook.assert_not_awaited()
