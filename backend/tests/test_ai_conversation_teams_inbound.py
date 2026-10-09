import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services import ai_conversation_teams_inbound as inbound


@pytest.fixture(autouse=True)
def clear_replay_proof_latches():
    with inbound._replay_proof_lock:
        inbound._replay_proof_deadlines.clear()
    yield
    with inbound._replay_proof_lock:
        inbound._replay_proof_deadlines.clear()


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


def test_fingerprint_da_activity_e_estavel_e_nao_expoe_identificador():
    fingerprint = inbound._activity_id_sha256('activity-1')

    assert fingerprint == inbound._activity_id_sha256(' activity-1 ')
    assert fingerprint == 'c1ffeee4d0eed82b7a24ac012710ea9dcdce15c71931cdf168ac3aca88505d1a'
    assert 'activity-1' not in fingerprint
    assert inbound._activity_id_sha256('') is None


def test_gatilho_replay_e_one_shot_escopado_e_expira(monkeypatch):
    clock = {'now': 100.0}
    monkeypatch.setattr(inbound.time, 'monotonic', lambda: clock['now'])

    ttl = inbound.armar_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
        ttl_seconds=45,
    )

    assert ttl == 45
    assert inbound._consumir_prova_replay_teams(
        usuario_aad_object_id='aad-other',
        teams_conversation_id='teams-conversation-1',
    ) is False
    assert inbound._consumir_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
    ) is True
    assert inbound._consumir_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
    ) is False

    inbound.armar_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
        ttl_seconds=30,
    )
    clock['now'] = 131.0
    assert inbound._consumir_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
    ) is False


def test_gatilho_reprocessa_mesma_activity_sem_segunda_resposta_ou_provedor():
    db = MagicMock()
    conversa = _conversation()
    resposta = SimpleNamespace(content='Resposta do ReqSys')
    enviar = AsyncMock()
    executar = MagicMock(
        side_effect=[
            {'mensagem_assistente': resposta, 'duplicado': False},
            {'mensagem_assistente': resposta, 'duplicado': True},
        ]
    )
    registrar = MagicMock()
    activity = _activity(activity_id='activity-real-1')
    inbound.armar_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
    )

    with (
        patch.object(inbound, '_conversa_recente', return_value=conversa),
        patch.object(inbound, 'executar_turno', executar),
        patch.object(inbound, '_responder_no_chat', enviar),
        patch.object(inbound, 'registrar_evento', registrar),
    ):
        result = asyncio.run(inbound.processar_activity_teams_bot(db, activity))

    assert executar.call_count == 2
    assert {
        call.kwargs['idempotency_key'] for call in executar.call_args_list
    } == {'teams-activity:activity-real-1'}
    enviar.assert_awaited_once()
    payloads = [json.loads(call.kwargs['payload_minimo']) for call in registrar.call_args_list]
    assert len(payloads) == 2
    assert payloads[0]['activity_id_sha256'] == payloads[1]['activity_id_sha256']
    assert payloads[0]['duplicate'] is False
    assert payloads[0]['provider_invoked'] is True
    assert payloads[0]['response_sent'] is True
    assert payloads[1]['duplicate'] is True
    assert payloads[1]['provider_invoked'] is False
    assert payloads[1]['response_sent'] is False
    assert result['replay_proof'] == {
        'requested': True,
        'duplicate': True,
        'response_sent': False,
    }


def test_gatilho_suprime_segunda_resposta_mesmo_se_idempotencia_regredir():
    db = MagicMock()
    conversa = _conversation()
    resposta = SimpleNamespace(content='Resposta do ReqSys')
    enviar = AsyncMock()
    executar = MagicMock(
        side_effect=[
            {'mensagem_assistente': resposta, 'duplicado': False},
            {'mensagem_assistente': resposta, 'duplicado': False},
        ]
    )
    registrar = MagicMock()
    inbound.armar_prova_replay_teams(
        usuario_aad_object_id='aad-user-1',
        teams_conversation_id='teams-conversation-1',
    )

    with (
        patch.object(inbound, '_conversa_recente', return_value=conversa),
        patch.object(inbound, 'executar_turno', executar),
        patch.object(inbound, '_responder_no_chat', enviar),
        patch.object(inbound, 'registrar_evento', registrar),
    ):
        result = asyncio.run(inbound.processar_activity_teams_bot(db, _activity()))

    enviar.assert_awaited_once()
    second_payload = json.loads(registrar.call_args_list[1].kwargs['payload_minimo'])
    assert second_payload['duplicate'] is False
    assert second_payload['provider_invoked'] is True
    assert second_payload['response_sent'] is False
    assert result['replay_proof']['duplicate'] is False


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
        patch.object(inbound, 'registrar_evento') as registrar,
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
    audit_payload = json.loads(registrar.call_args.kwargs['payload_minimo'])
    assert audit_payload == {
        'activity_id_sha256': inbound._activity_id_sha256('activity-1'),
        'channel': 'teams_bot',
        'duplicate': False,
        'latency_ms': audit_payload['latency_ms'],
        'provider_invoked': True,
        'response_sent': True,
        'status': 'completed',
    }
    assert audit_payload['latency_ms'] >= 0


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
        patch.object(inbound, 'registrar_evento') as registrar,
    ):
        result = asyncio.run(inbound.processar_activity_teams_bot(db, _activity()))

    assert result['duplicado'] is True
    enviar.assert_not_awaited()
    audit_payload = json.loads(registrar.call_args.kwargs['payload_minimo'])
    assert audit_payload['activity_id_sha256'] == inbound._activity_id_sha256('activity-1')
    assert audit_payload['duplicate'] is True
    assert audit_payload['provider_invoked'] is False
    assert audit_payload['response_sent'] is False


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
        patch.object(inbound, 'registrar_evento') as registrar,
    ):
        asyncio.run(inbound.processar_activity_teams_bot_background(_activity()))

    notificar.assert_awaited_once()
    assert 'segredo-que-nao-pode-vazar' not in notificar.await_args.kwargs['resposta']
    audit_payload = json.loads(registrar.call_args.kwargs['payload_minimo'])
    assert audit_payload['status'] == 'failed'
    assert audit_payload['activity_id_sha256'] == inbound._activity_id_sha256('activity-1')
    assert audit_payload['channel'] == 'teams_bot'
    assert audit_payload['error_category'] == 'RuntimeError'
    assert audit_payload['latency_ms'] >= 0
    assert 'segredo-que-nao-pode-vazar' not in registrar.call_args.kwargs['payload_minimo']
    db.close.assert_called_once()


def test_background_notifica_usuario_mesmo_se_auditoria_falhar():
    db = MagicMock()
    notificar = AsyncMock()

    with (
        patch.object(inbound, 'SessionLocal', return_value=db),
        patch.object(
            inbound,
            'processar_activity_teams_bot',
            AsyncMock(side_effect=RuntimeError('falha-do-runtime')),
        ),
        patch.object(inbound, '_responder_no_chat', notificar),
        patch.object(inbound, 'registrar_evento', side_effect=SQLAlchemyError('db-offline')),
    ):
        asyncio.run(inbound.processar_activity_teams_bot_background(_activity()))

    db.rollback.assert_called_once()
    notificar.assert_awaited_once()
    assert 'falha-do-runtime' not in notificar.await_args.kwargs['resposta']
    assert 'db-offline' not in notificar.await_args.kwargs['resposta']
    db.close.assert_called_once()
