"""Testes do canal 'bot' (Azure Bot Service / Bot Framework) do Teams Messaging Gateway."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.teams_gateway import TeamsGatewayMessageRequest
from app.services import teams_gateway as svc


def _run(coro):
    return asyncio.run(coro)


def _configurar_bot(monkeypatch, configurado: bool = True) -> None:
    monkeypatch.setattr(svc.settings, 'teams_bot_app_id', 'bot-app-id' if configurado else '')
    monkeypatch.setattr(svc.settings, 'teams_bot_app_tenant_id', 'bot-tenant-id' if configurado else '')
    monkeypatch.setattr(svc.settings, 'teams_bot_secret', 'bot-secret' if configurado else '')


def test_status_gateway_bot_reflete_configuracao_real(monkeypatch):
    _configurar_bot(monkeypatch, configurado=False)

    status = svc.status_gateway()

    rota_bot = next(rota for rota in status['rotas'] if rota['canal'] == 'bot')
    assert rota_bot['disponivel'] is False
    assert 'TEAMS_BOT_APP_ID' in rota_bot['campos_faltantes']

    _configurar_bot(monkeypatch, configurado=True)
    status = svc.status_gateway()
    rota_bot = next(rota for rota in status['rotas'] if rota['canal'] == 'bot')
    assert rota_bot['disponivel'] is True
    assert rota_bot['campos_faltantes'] == []


def test_deve_usar_bot_modo_explicito_mesmo_sem_configuracao(monkeypatch):
    _configurar_bot(monkeypatch, configurado=False)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola', modo='bot')

    assert svc._deve_usar_bot(payload) is True


def test_deve_usar_bot_auto_sem_token_e_com_bot_configurado(monkeypatch):
    _configurar_bot(monkeypatch, configurado=True)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola')

    assert svc._deve_usar_bot(payload) is True


def test_selecionar_rota_prefere_bot_quando_configurado_e_sem_token(monkeypatch):
    _configurar_bot(monkeypatch, configurado=True)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola')

    rota = svc.selecionar_rota(payload)

    assert rota['canal'] == 'bot'


def test_enviar_gateway_bot_nao_configurado_retorna_erro_claro(monkeypatch):
    _configurar_bot(monkeypatch, configurado=False)
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola', modo='bot')

    resultado = _run(svc.enviar_mensagem_gateway(payload, correlation_id='corr-bot-1'))

    assert resultado['entregue'] is False
    assert resultado['canal_usado'] == 'bot'
    assert 'TEAMS_BOT_APP_ID' in resultado['erro']


def test_enviar_gateway_bot_sem_conversa_referencia_bloqueia_com_mensagem_clara(monkeypatch):
    _configurar_bot(monkeypatch, configurado=True)
    fake_db = MagicMock()
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola', modo='bot')

    with patch('app.services.teams_gateway.obter_conversa_referencia_bot', return_value=None) as mock_obter:
        resultado = _run(svc.enviar_mensagem_gateway(payload, db=fake_db, correlation_id='corr-bot-2'))

    mock_obter.assert_called_once_with(fake_db, 'aad-1')
    assert resultado['entregue'] is False
    assert resultado['canal_usado'] == 'bot'
    assert resultado['motivo'] == 'conversa_bot_nao_instalada'


@patch('app.services.teams_gateway._enviar_atividade_bot_framework', new_callable=AsyncMock)
@patch('app.services.teams_gateway.obter_conversa_referencia_bot')
def test_enviar_gateway_bot_sucesso(mock_obter_referencia, mock_enviar_atividade, monkeypatch):
    _configurar_bot(monkeypatch, configurado=True)
    referencia = MagicMock(service_url='https://smba.trafficmanager.net/br/', conversation_id='conv-1')
    mock_obter_referencia.return_value = referencia
    mock_enviar_atividade.return_value = {'id': 'activity-1'}
    fake_db = MagicMock()
    payload = TeamsGatewayMessageRequest(destino_tipo='chat', destino_id='aad-1', texto='Ola via bot', modo='bot')

    resultado = _run(svc.enviar_mensagem_gateway(payload, db=fake_db, correlation_id='corr-bot-3'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'bot'
    assert resultado['message_id'] == 'activity-1'
    assert resultado['chat_id'] == 'conv-1'
    mock_enviar_atividade.assert_awaited_once()
    url_chamada, payload_chamado = mock_enviar_atividade.await_args.args
    assert url_chamada == 'https://smba.trafficmanager.net/br/v3/conversations/conv-1/activities'
    assert payload_chamado['text'] == 'Ola via bot'


@patch('app.services.teams_gateway._enviar_webhook', new_callable=AsyncMock)
@patch('app.services.teams_gateway._enviar_atividade_bot_framework', new_callable=AsyncMock)
@patch('app.services.teams_gateway.obter_conversa_referencia_bot')
def test_enviar_gateway_bot_fallback_para_webhook(mock_obter_referencia, mock_enviar_atividade, mock_webhook, monkeypatch):
    _configurar_bot(monkeypatch, configurado=True)
    mock_obter_referencia.return_value = None
    mock_webhook.return_value = {'status_code': 200}
    fake_db = MagicMock()
    payload = TeamsGatewayMessageRequest(
        destino_tipo='chat',
        destino_id='aad-1',
        texto='Fallback via bot',
        modo='bot',
        webhook_url='https://example.invalid/webhook',
        permitir_fallback=True,
    )

    resultado = _run(svc.enviar_mensagem_gateway(payload, db=fake_db, correlation_id='corr-bot-4'))

    assert resultado['entregue'] is True
    assert resultado['canal_usado'] == 'webhook'
    assert resultado['fallback_usado'] is True
    mock_enviar_atividade.assert_not_awaited()
    mock_webhook.assert_awaited_once()


def test_salvar_e_obter_conversa_referencia_bot_upsert():
    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        svc.salvar_conversa_referencia_bot(
            db,
            usuario_aad_object_id='aad-upsert-1',
            service_url='https://smba.trafficmanager.net/br/',
            conversation_id='conv-antiga',
        )
        item = svc.salvar_conversa_referencia_bot(
            db,
            usuario_aad_object_id='aad-upsert-1',
            service_url='https://smba.trafficmanager.net/br/',
            conversation_id='conv-nova',
        )

        encontrado = svc.obter_conversa_referencia_bot(db, 'aad-upsert-1')

        assert item.conversation_id == 'conv-nova'
        assert encontrado is not None
        assert encontrado.conversation_id == 'conv-nova'
    finally:
        db.query(svc.BotConversaReferencia).filter_by(usuario_aad_object_id='aad-upsert-1').delete()
        db.commit()
        db.close()
