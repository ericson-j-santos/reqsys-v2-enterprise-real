import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import ai_conversation_teams_inbound as inbound


def _activity(*, activity_id='activity-1', text='Olá ReqSys'):
    return {
        'id': activity_id,
        'type': 'message',
        'text': text,
        'from': {'aadObjectId': 'aad-user-1'},
        'recipient': {'id': '28:bot-id'},
        'conversation': {'id': 'teams-conversation-1'},
        'channelData': {'tenant': {'id': 'tenant-1'}},
    }


def _conversation():
    return SimpleNamespace(
        id='conversation-1',
        teams_destino_id='aad-user-1',
        teams_destino_tipo='chat_1a1',
        teams_modo='bot',
        status='aguardando_usuario',
    )


def test_selecionar_provedor_teams_faz_fallback_para_ollama(monkeypatch):
    monkeypatch.setattr(inbound.settings, 'ai_default_provider', 'gemini')
    monkeypatch.setattr(inbound.settings, 'codex_ollama_model', 'qwen-test')
    monkeypatch.setattr(
        inbound,
        'status_provedores',
        lambda: {
            'gemini': {'configurado': False},
            'ollama': {'configurado': True},
        },
    )

    assert inbound.selecionar_provedor_teams() == ('ollama', 'qwen-test')


def test_identificador_de_contexto_e_estavel_e_isolado_por_chat():
    chat_1 = inbound._teams_chat_area_id('teams-conversation-1')
    chat_2 = inbound._teams_chat_area_id('teams-conversation-2')

    assert chat_1 == inbound._teams_chat_area_id('teams-conversation-1')
    assert chat_1.startswith('teams-inbound:')
    assert chat_1 != chat_2


def test_processar_mensagem_comum_reutiliza_conversa_e_responde_no_chat():
    db = MagicMock()
    conversa = _conversation()
    resposta = SimpleNamespace(content='Resposta do ReqSys')
    enviar = AsyncMock()

    with (
        patch.object(inbound, '_conversa_recente', return_value=conversa) as recente,
        patch.object(
            inbound,
            'executar_turno',
            return_value={'mensagem_assistente': resposta, 'duplicado': False},
        ) as executar,
        patch.object(inbound, '_responder_no_chat', enviar),
        patch.object(inbound, 'registrar_evento'),
    ):
        result = asyncio.run(inbound.processar_activity_teams_bot(db, _activity()))

    assert result['processado'] is True
    assert result['conversation_id'] == 'conversation-1'
    assert result['duplicado'] is False
    assert executar.call_args.kwargs['idempotency_key'] == 'teams-activity:activity-1'
    assert recente.call_args.kwargs['teams_chat_area_id'] == (
        inbound._teams_chat_area_id('teams-conversation-1')
    )
    enviar.assert_awaited_once()
    assert enviar.await_args.kwargs['resposta'] == 'Resposta do ReqSys'


def test_processar_retry_idempotente_nao_reenvia_resposta():
    db = MagicMock()
    conversa = _conversation()
    resposta = SimpleNamespace(content='Resposta já entregue')
    enviar = AsyncMock()

    with (
        patch.object(inbound, '_conversa_recente', return_value=conversa),
        patch.object(
            inbound,
            'executar_turno',
            return_value={'mensagem_assistente': resposta, 'duplicado': True},
        ),
        patch.object(inbound, '_responder_no_chat', enviar),
        patch.object(inbound, 'registrar_evento'),
    ):
        result = asyncio.run(inbound.processar_activity_teams_bot(db, _activity()))

    assert result['duplicado'] is True
    enviar.assert_not_awaited()


def test_mensagem_em_chat_sem_contexto_cria_conversa_isolada():
    db = MagicMock()
    conversa = _conversation()
    resposta = SimpleNamespace(content='Contexto novo')

    with (
        patch.object(inbound, '_conversa_recente', return_value=None),
        patch.object(inbound, '_criar_conversa_teams', return_value=conversa) as criar,
        patch.object(
            inbound,
            'executar_turno',
            return_value={'mensagem_assistente': resposta, 'duplicado': False},
        ),
        patch.object(inbound, '_responder_no_chat', AsyncMock()),
        patch.object(inbound, 'registrar_evento'),
    ):
        asyncio.run(inbound.processar_activity_teams_bot(db, _activity(text='Novo assunto')))

    assert criar.call_args.kwargs['teams_chat_area_id'] == inbound._teams_chat_area_id(
        'teams-conversation-1'
    )


def test_submit_de_cartao_bloqueia_remetente_diferente():
    db = MagicMock()
    conversa = _conversation()
    conversa.teams_destino_id = 'aad-owner'
    activity = _activity()
    activity['value'] = {
        'reqsys_action': 'ai_conversation_reply',
        'conversation_id': 'conversation-1',
        'mensagem': 'Continue',
    }

    with (
        patch.object(inbound, 'obter_conversa', return_value=conversa),
        patch.object(inbound, 'registrar_evento'),
        pytest.raises(RuntimeError, match='teams_inbound_sender_mismatch'),
    ):
        asyncio.run(inbound.processar_activity_teams_bot(db, activity))


def test_background_notifica_falha_sem_expor_excecao():
    db = MagicMock()
    notificar = AsyncMock()

    with (
        patch.object(inbound, 'SessionLocal', return_value=db),
        patch.object(
            inbound,
            'processar_activity_teams_bot',
            AsyncMock(side_effect=RuntimeError('segredo-que-nao-pode-vazar')),
        ),
        patch.object(inbound, '_responder_no_chat', notificar),
    ):
        asyncio.run(inbound.processar_activity_teams_bot_background(_activity()))

    notificar.assert_awaited_once()
    assert 'segredo-que-nao-pode-vazar' not in notificar.await_args.kwargs['resposta']
    db.close.assert_called_once()
