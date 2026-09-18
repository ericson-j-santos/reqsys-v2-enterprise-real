import json

import pytest

from app.schemas.ai_conversation import AIConversationCreateRequest
from app.services.ai_conversation import (
    AIConversationConflictError,
    criar_conversa,
    executar_turno,
    listar_mensagens,
    status_provedores,
)


class FakeGateway:
    def __init__(self):
        self.calls = []

    def gerar_openai(self, **kwargs):
        self.calls.append(kwargs)
        return f"resposta-{len(self.calls)}"


def _payload(**overrides):
    data = {
        'provider': 'openai',
        'model': 'gpt-test',
        'mensagem': 'Primeira pergunta',
        'titulo': 'Teste Teams bidirecional',
        'teams_destino_tipo': 'chat_1a1',
        'teams_destino_id': 'aad-user-test',
        'teams_modo': 'bot',
    }
    data.update(overrides)
    return AIConversationCreateRequest(**data)


def test_turno_persiste_historico_e_enfileira_cartao(db_session):
    payload = _payload()
    conversa = criar_conversa(db_session, payload, correlation_id='corr-1')
    gateway = FakeGateway()

    result = executar_turno(
        db_session,
        conversa=conversa,
        mensagem=payload.mensagem,
        correlation_id='corr-1',
        idempotency_key='turn-1',
        origem='teste',
        enviar_teams=True,
        gateway=gateway,
        env={'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
    )

    mensagens = listar_mensagens(db_session, conversa.id)
    assert [item.role for item in mensagens] == ['user', 'assistant']
    assert mensagens[-1].content == 'resposta-1'
    assert conversa.status == 'aguardando_usuario'
    assert len(gateway.calls) == 1

    notificacao = result['notificacao']
    assert notificacao is not None
    metadata = json.loads(notificacao.metadata_json)
    card = metadata['adaptiveCard']
    assert card['actions'][0]['data']['reqsys_action'] == 'ai_conversation_reply'
    assert card['actions'][0]['data']['conversation_id'] == conversa.id
    assert any(
        item.get('id') == 'mensagem'
        for item in card['body']
        if item.get('type') == 'Input.Text'
    )


def test_idempotencia_nao_duplica_chamada_ao_modelo(db_session):
    payload = _payload()
    conversa = criar_conversa(db_session, payload, correlation_id='corr-2')
    gateway = FakeGateway()
    kwargs = {
        'db': db_session,
        'conversa': conversa,
        'mensagem': 'Executar apenas uma vez',
        'correlation_id': 'corr-2',
        'idempotency_key': 'teams-activity:123',
        'origem': 'teams',
        'enviar_teams': False,
        'gateway': gateway,
        'env': {'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
    }

    first = executar_turno(**kwargs)
    second = executar_turno(**kwargs)

    assert first['duplicado'] is False
    assert second['duplicado'] is True
    assert first['mensagem_assistente'].content == second['mensagem_assistente'].content
    assert len(gateway.calls) == 1
    assert len(listar_mensagens(db_session, conversa.id)) == 2


def test_mesma_chave_com_conteudo_diferente_e_rejeitada(db_session):
    payload = _payload()
    conversa = criar_conversa(db_session, payload, correlation_id='corr-3')
    gateway = FakeGateway()

    executar_turno(
        db_session,
        conversa=conversa,
        mensagem='Conteúdo A',
        correlation_id='corr-3',
        idempotency_key='same-key',
        origem='teams',
        enviar_teams=False,
        gateway=gateway,
        env={'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
    )

    with pytest.raises(AIConversationConflictError):
        executar_turno(
            db_session,
            conversa=conversa,
            mensagem='Conteúdo B',
            correlation_id='corr-3',
            idempotency_key='same-key',
            origem='teams',
            enviar_teams=False,
            gateway=gateway,
            env={'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
        )

    assert len(gateway.calls) == 1


def test_turno_seguinte_recebe_historico_anterior(db_session):
    payload = _payload()
    conversa = criar_conversa(db_session, payload, correlation_id='corr-4')
    gateway = FakeGateway()
    env = {'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'}

    executar_turno(
        db_session,
        conversa=conversa,
        mensagem='Pergunta um',
        correlation_id='corr-4',
        idempotency_key='turn-a',
        origem='api',
        enviar_teams=False,
        gateway=gateway,
        env=env,
    )
    executar_turno(
        db_session,
        conversa=conversa,
        mensagem='Pergunta dois',
        correlation_id='corr-5',
        idempotency_key='turn-b',
        origem='teams',
        enviar_teams=False,
        gateway=gateway,
        env=env,
    )

    segundo_prompt = gateway.calls[1]['prompt']
    assert 'USER: Pergunta um' in segundo_prompt
    assert 'ASSISTANT: resposta-1' in segundo_prompt
    assert 'USER: Pergunta dois' in segundo_prompt


def test_status_provedores_nao_expoe_credenciais():
    status = status_provedores(
        {
            'AI_CONVERSATION_OPENAI_API_KEY': 'segredo',
            'AI_CONVERSATION_OLLAMA_BASE_URL': 'http://localhost:11434',
        }
    )

    assert status['openai'] == {'configurado': True}
    assert status['ollama'] == {'configurado': True}
    assert status['claude'] == {'configurado': False}
    assert 'segredo' not in json.dumps(status)
