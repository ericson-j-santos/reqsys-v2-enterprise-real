import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import ai_conversation as api
from app.core.service_tokens import ServiceAuthContext
from app.db import get_db
from app.main import app
from app.services.ai_conversation import (
    AIConversationConflictError,
    AIConversationError,
    AIConversationNotFoundError,
    AIProviderConfigurationError,
    AIProviderExecutionError,
)
from app.services.ai_conversation_teams_bot import AITeamsBotDeliveryError

client = TestClient(app)


@pytest.fixture
def api_overrides():
    db = MagicMock()
    app.dependency_overrides[api.require_ai_conversation_auth] = lambda: ServiceAuthContext(
        ator='admin@teste',
        via_token=False,
    )
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(api.require_ai_conversation_auth, None)
    app.dependency_overrides.pop(get_db, None)


def _conversation(**overrides):
    data = {
        'id': 'conv-1',
        'provider': 'openai',
        'model': 'gpt-test',
        'titulo': 'Conversa teste',
        'teams_destino_id': 'aad-user-1',
        'teams_destino_tipo': 'chat_1a1',
        'teams_modo': 'bot',
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _turn_result(content='resposta-ok', duplicate=False):
    return {
        'mensagem_assistente': SimpleNamespace(content=content),
        'duplicado': duplicate,
    }


@pytest.mark.parametrize(
    ('exc', 'status_code'),
    [
        (AIConversationNotFoundError('não encontrada'), 404),
        (AIConversationConflictError('conflito'), 409),
        (AIProviderConfigurationError('sem configuração'), 503),
        (AIProviderExecutionError('falha provider'), 502),
        (AIConversationError('genérico'), 500),
    ],
)
def test_http_error_mapeia_erros_de_dominio(exc, status_code):
    http_error = api._http_error(exc)

    assert http_error.status_code == status_code


def test_entrega_teams_desabilitada_retorna_none():
    result = asyncio.run(
        api._entregar_resposta_teams(
            MagicMock(),
            conversa=_conversation(),
            resposta='resposta',
            correlation_id='corr-1',
            habilitado=False,
        )
    )

    assert result is None


def test_entrega_teams_prioriza_bot_direto(monkeypatch):
    bot = AsyncMock(return_value={'entregue': True, 'message_id': 'msg-1'})
    monkeypatch.setattr(api, 'enviar_cartao_conversa_bot', bot)

    result = asyncio.run(
        api._entregar_resposta_teams(
            MagicMock(),
            conversa=_conversation(),
            resposta='resposta',
            correlation_id='corr-2',
            habilitado=True,
        )
    )

    assert result['modo'] == 'bot_adaptive_card'
    assert result['entrega']['message_id'] == 'msg-1'


@pytest.mark.parametrize(
    'direct_error',
    [AITeamsBotDeliveryError('sem referência'), RuntimeError('falha inesperada')],
)
def test_entrega_teams_faz_fallback_para_fila(monkeypatch, direct_error):
    db = MagicMock()
    conversa = _conversation()
    item = SimpleNamespace(id=55)
    monkeypatch.setattr(
        api,
        'enviar_cartao_conversa_bot',
        AsyncMock(side_effect=direct_error),
    )
    monkeypatch.setattr(api, '_enfileirar_teams', lambda *args, **kwargs: item)
    monkeypatch.setattr(api, 'executar_item_fila', AsyncMock(return_value=item))
    monkeypatch.setattr(api, 'serializar_item', lambda value: {'id': value.id})

    result = asyncio.run(
        api._entregar_resposta_teams(
            db,
            conversa=conversa,
            resposta='resposta',
            correlation_id='corr-3',
            habilitado=True,
        )
    )

    assert result == {
        'modo': 'fila_gateway',
        'entrega': None,
        'fila': {'id': 55},
    }


def test_status_expoe_contrato_sem_segredos(api_overrides, monkeypatch):
    monkeypatch.setattr(
        api,
        'status_provedores',
        lambda: {'openai': {'configurado': True}},
    )

    response = client.get('/v1/teams-gateway/ai-conversations/status')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['schema_version'] == '1.2.0'
    assert data['providers']['openai']['configurado'] is True
    assert data['teams_reply_contract']['action'] == 'ai_conversation_reply'


def test_create_executa_turno_audita_e_entrega_teams(api_overrides, monkeypatch):
    conversa = _conversation()
    registrar = MagicMock()
    monkeypatch.setattr(api, 'criar_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(api, 'executar_turno', lambda *args, **kwargs: _turn_result())
    monkeypatch.setattr(api, 'registrar_evento', registrar)
    monkeypatch.setattr(
        api,
        '_entregar_resposta_teams',
        AsyncMock(return_value={'modo': 'bot_adaptive_card'}),
    )
    monkeypatch.setattr(api, 'serializar_conversa', lambda *args, **kwargs: {'id': 'conv-1'})

    response = client.post(
        '/v1/teams-gateway/ai-conversations',
        headers={'X-Correlation-ID': 'corr-create'},
        json={
            'provider': 'openai',
            'model': 'gpt-test',
            'mensagem': 'Primeira pergunta',
            'teams_destino_tipo': 'chat_1a1',
            'teams_destino_id': 'aad-user-1',
            'teams_modo': 'bot',
            'enviar_teams': True,
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['conversation']['id'] == 'conv-1'
    assert response.json()['data']['response'] == 'resposta-ok'
    assert registrar.call_count == 2


def test_create_traduz_falha_do_provider_para_503(api_overrides, monkeypatch):
    conversa = _conversation()
    registrar = MagicMock()
    monkeypatch.setattr(api, 'criar_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(
        api,
        'executar_turno',
        MagicMock(side_effect=AIProviderConfigurationError('provider não configurado')),
    )
    monkeypatch.setattr(api, 'registrar_evento', registrar)

    response = client.post(
        '/v1/teams-gateway/ai-conversations',
        json={
            'provider': 'openai',
            'model': 'gpt-test',
            'mensagem': 'Pergunta',
            'enviar_teams': False,
        },
    )

    assert response.status_code == 503
    assert registrar.call_count == 2


def test_get_retorna_conversa_serializada(api_overrides, monkeypatch):
    conversa = _conversation()
    monkeypatch.setattr(api, 'obter_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(
        api,
        'serializar_conversa',
        lambda *args, **kwargs: {'id': conversa.id, 'status': 'aguardando_usuario'},
    )

    response = client.get('/v1/teams-gateway/ai-conversations/conv-1')

    assert response.status_code == 200
    assert response.json()['data']['id'] == 'conv-1'


def test_get_retorna_404_para_conversa_inexistente(api_overrides, monkeypatch):
    monkeypatch.setattr(
        api,
        'obter_conversa',
        MagicMock(side_effect=AIConversationNotFoundError('não encontrada')),
    )

    response = client.get('/v1/teams-gateway/ai-conversations/inexistente')

    assert response.status_code == 404


def test_reply_continua_mesma_conversa(api_overrides, monkeypatch):
    conversa = _conversation()
    registrar = MagicMock()
    executar = MagicMock(return_value=_turn_result(content='segunda resposta'))
    monkeypatch.setattr(api, 'obter_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(api, 'executar_turno', executar)
    monkeypatch.setattr(api, 'registrar_evento', registrar)
    monkeypatch.setattr(
        api,
        '_entregar_resposta_teams',
        AsyncMock(return_value={'modo': 'bot_adaptive_card'}),
    )

    response = client.post(
        '/v1/teams-gateway/ai-conversations/conv-1/reply',
        headers={'X-Correlation-ID': 'corr-reply'},
        json={
            'mensagem': 'Continue',
            'idempotency_key': 'turn-2',
            'origem': 'api',
            'enviar_teams': True,
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['conversation_id'] == 'conv-1'
    assert response.json()['data']['response'] == 'segunda resposta'
    assert executar.call_args.kwargs['conversa'] is conversa
    assert registrar.call_count == 1


def test_reply_traduz_conflito_para_409(api_overrides, monkeypatch):
    conversa = _conversation()
    monkeypatch.setattr(api, 'obter_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(
        api,
        'executar_turno',
        MagicMock(side_effect=AIConversationConflictError('turno duplicado incompleto')),
    )
    monkeypatch.setattr(api, 'registrar_evento', MagicMock())

    response = client.post(
        '/v1/teams-gateway/ai-conversations/conv-1/reply',
        json={'mensagem': 'Continue', 'enviar_teams': False},
    )

    assert response.status_code == 409


def test_bot_sem_token_retorna_401(api_overrides):
    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        json={'type': 'message'},
    )

    assert response.status_code == 401


def test_bot_token_invalido_retorna_401(api_overrides, monkeypatch):
    monkeypatch.setattr(
        api,
        'validar_jwt_bot_framework',
        MagicMock(side_effect=ValueError('jwt inválido')),
    )

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-invalido'},
        json={'type': 'message'},
    )

    assert response.status_code == 401


def test_bot_evento_comum_persiste_referencia_sem_chamar_ia(api_overrides, monkeypatch):
    salvar = MagicMock()
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})
    monkeypatch.setattr(api, 'salvar_conversa_referencia_bot', salvar)

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'type': 'conversationUpdate',
            'serviceUrl': 'https://smba.trafficmanager.net/br/',
            'from': {'id': '29:user', 'aadObjectId': 'aad-user-1'},
            'recipient': {'id': '28:bot'},
            'conversation': {'id': 'a:teams-1'},
            'channelData': {'tenant': {'id': 'tenant-1'}},
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['acao_ia'] is False
    salvar.assert_called_once()


def test_bot_submit_exige_conversa_e_mensagem(api_overrides, monkeypatch):
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'type': 'message',
            'from': {'aadObjectId': 'aad-user-1'},
            'value': {'reqsys_action': 'ai_conversation_reply'},
        },
    )

    assert response.status_code == 422


def test_bot_submit_exige_identidade_aad(api_overrides, monkeypatch):
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'type': 'message',
            'value': {
                'reqsys_action': 'ai_conversation_reply',
                'conversation_id': 'conv-1',
                'mensagem': 'continue',
            },
        },
    )

    assert response.status_code == 403


def test_bot_submit_bloqueia_usuario_nao_associado(api_overrides, monkeypatch):
    registrar = MagicMock()
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})
    monkeypatch.setattr(
        api,
        'obter_conversa',
        lambda *args, **kwargs: _conversation(teams_destino_id='aad-owner'),
    )
    monkeypatch.setattr(api, 'registrar_evento', registrar)

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'type': 'message',
            'from': {'aadObjectId': 'aad-invasor'},
            'value': {
                'reqsys_action': 'ai_conversation_reply',
                'conversation_id': 'conv-1',
                'mensagem': 'continue',
                'correlation_id': 'corr-denied',
            },
        },
    )

    assert response.status_code == 403
    registrar.assert_called_once()


def test_bot_submit_traduz_conversa_inexistente_para_404(api_overrides, monkeypatch):
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})
    monkeypatch.setattr(
        api,
        'obter_conversa',
        MagicMock(side_effect=AIConversationNotFoundError('não encontrada')),
    )

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'type': 'message',
            'from': {'aadObjectId': 'aad-user-1'},
            'value': {
                'reqsys_action': 'ai_conversation_reply',
                'conversation_id': 'conv-inexistente',
                'mensagem': 'continue',
            },
        },
    )

    assert response.status_code == 404


def test_bot_submit_valido_continua_turno_idempotente(api_overrides, monkeypatch):
    db = api_overrides
    conversa = _conversation(teams_destino_id='aad-user-1')
    executar = MagicMock(return_value=_turn_result(content='resposta teams'))
    registrar = MagicMock()
    monkeypatch.setattr(api, 'validar_jwt_bot_framework', lambda token: {'aud': 'bot'})
    monkeypatch.setattr(api, 'salvar_conversa_referencia_bot', MagicMock())
    monkeypatch.setattr(api, 'obter_conversa', lambda *args, **kwargs: conversa)
    monkeypatch.setattr(api, 'executar_turno', executar)
    monkeypatch.setattr(api, 'registrar_evento', registrar)
    monkeypatch.setattr(
        api,
        '_entregar_resposta_teams',
        AsyncMock(return_value={'modo': 'bot_adaptive_card'}),
    )

    response = client.post(
        '/v1/teams-gateway/ai-conversations/bot/messages',
        headers={'Authorization': 'Bearer token-valido'},
        json={
            'id': 'activity-123',
            'type': 'message',
            'serviceUrl': 'https://smba.trafficmanager.net/br/',
            'from': {'id': '29:user', 'aadObjectId': 'aad-user-1'},
            'recipient': {'id': '28:bot'},
            'conversation': {'id': 'a:teams-1'},
            'channelData': {'tenant': {'id': 'tenant-1'}},
            'value': {
                'reqsys_action': 'ai_conversation_reply',
                'conversation_id': 'conv-1',
                'mensagem': 'continue',
                'correlation_id': 'corr-bot',
            },
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['acao_ia'] is True
    assert data['conversation_id'] == 'conv-1'
    assert executar.call_args.kwargs['idempotency_key'] == 'teams-activity:activity-123'
    assert conversa.teams_modo == 'bot'
    db.commit.assert_called()
    registrar.assert_called_once()
