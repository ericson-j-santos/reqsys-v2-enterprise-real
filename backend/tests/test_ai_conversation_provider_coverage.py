from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.ai_conversation import AIConversationCreateRequest
from app.services.ai_conversation import (
    AIProviderConfigurationError,
    AIProviderExecutionError,
    _chamar_provider,
    _classification_lock,
    _env_int,
    criar_conversa,
    executar_turno,
    serializar_conversa,
)


class OpenAIGateway:
    def gerar_openai(self, **kwargs):
        return 'resposta serializada'


def _conversa_provider(provider: str, *, conversation_id: str = 'conv-provider') -> SimpleNamespace:
    data_classification = 'internal'
    return SimpleNamespace(
        id=conversation_id,
        provider=provider,
        model='modelo-teste',
        requested_provider=provider,
        authorized_provider=provider,
        data_classification=data_classification,
        classification_lock_sha256=_classification_lock(conversation_id, data_classification),
        policy_mode='off',
        policy_decision='allowed',
        policy_reason='legacy_policy_mode_off',
        policy_correlation_id='corr-provider',
    )


def test_env_int_aplica_default_invalido_e_limite_minimo():
    assert _env_int({}, 'TIMEOUT', 60) == 60
    assert _env_int({'TIMEOUT': 'invalido'}, 'TIMEOUT', 60) == 60
    assert _env_int({'TIMEOUT': '0'}, 'TIMEOUT', 60) == 1
    assert _env_int({'TIMEOUT': '15'}, 'TIMEOUT', 60) == 15


@pytest.mark.parametrize(
    ('provider', 'env', 'method_name'),
    [
        ('openai', {'AI_CONVERSATION_OPENAI_API_KEY': 'key'}, 'gerar_openai'),
        ('claude', {'AI_CONVERSATION_CLAUDE_API_KEY': 'key'}, 'gerar_claude'),
        ('gemini', {'AI_CONVERSATION_GEMINI_API_KEY': 'key'}, 'gerar_gemini'),
        ('groq', {'AI_CONVERSATION_GROQ_API_KEY': 'key'}, 'gerar_groq'),
        ('ollama', {'AI_CONVERSATION_OLLAMA_BASE_URL': 'http://ollama:11434'}, 'gerar_ollama'),
    ],
)
def test_chamar_provider_cobre_adaptadores_suportados(provider, env, method_name):
    conversa = _conversa_provider(provider)
    gateway = MagicMock()
    getattr(gateway, method_name).return_value = '  resposta válida  '

    resposta = _chamar_provider(
        conversa=conversa,
        prompt='prompt',
        gateway=gateway,
        env=env,
        correlation_id='corr-provider',
    )

    assert resposta == 'resposta válida'
    getattr(gateway, method_name).assert_called_once()


def test_chamar_provider_rejeita_configuracao_ausente():
    conversa = _conversa_provider('claude')

    with pytest.raises(AIProviderConfigurationError, match='não resolvido pelo cofre/configuração'):
        _chamar_provider(
            conversa=conversa,
            prompt='prompt',
            gateway=MagicMock(),
            env={},
            correlation_id='corr-provider',
        )


def test_chamar_provider_traduz_erro_do_sdk_sem_vazar_detalhe():
    conversa = _conversa_provider('openai')
    gateway = MagicMock()
    gateway.gerar_openai.side_effect = RuntimeError('segredo interno do SDK')

    with pytest.raises(AIProviderExecutionError) as exc_info:
        _chamar_provider(
            conversa=conversa,
            prompt='prompt',
            gateway=gateway,
            env={'AI_CONVERSATION_OPENAI_API_KEY': 'key'},
            correlation_id='corr-provider',
        )

    assert 'RuntimeError' in str(exc_info.value)
    assert 'segredo interno do SDK' not in str(exc_info.value)


def test_chamar_provider_rejeita_resposta_vazia():
    conversa = _conversa_provider('openai')
    gateway = MagicMock()
    gateway.gerar_openai.return_value = '   '

    with pytest.raises(AIProviderExecutionError, match='resposta vazia'):
        _chamar_provider(
            conversa=conversa,
            prompt='prompt',
            gateway=gateway,
            env={'AI_CONVERSATION_OPENAI_API_KEY': 'key'},
            correlation_id='corr-provider',
        )


def test_serializar_conversa_inclui_historico_e_metadados(db_session):
    payload = AIConversationCreateRequest(
        provider='openai',
        model='gpt-test',
        mensagem='Pergunta para serialização',
        titulo='Serialização governada',
        origem='teste',
        teams_destino_tipo='chat_1a1',
        teams_destino_id='aad-user-test',
        teams_modo='bot',
        enviar_teams=False,
    )
    conversa = criar_conversa(db_session, payload, correlation_id='corr-serializar')
    executar_turno(
        db_session,
        conversa=conversa,
        mensagem=payload.mensagem,
        correlation_id='corr-serializar',
        idempotency_key='serializar-turn-1',
        origem='teste',
        enviar_teams=False,
        gateway=OpenAIGateway(),
        env={'AI_CONVERSATION_OPENAI_API_KEY': 'fake-key'},
    )

    data = serializar_conversa(db_session, conversa)

    assert data['id'] == conversa.id
    assert data['provider'] == 'openai'
    assert data['model'] == 'gpt-test'
    assert data['status'] == 'aguardando_usuario'
    assert data['correlation_id'] == 'corr-serializar'
    assert data['criado_em'] is not None
    assert data['atualizado_em'] is not None
    assert data['ultima_mensagem_em'] is not None
    assert [item['role'] for item in data['mensagens']] == ['user', 'assistant']
    assert data['mensagens'][1]['content'] == 'resposta serializada'
    assert len(data['mensagens'][1]['content_sha256']) == 64


def test_serializar_conversa_pode_omitir_mensagens(db_session):
    payload = AIConversationCreateRequest(
        provider='openai',
        model='gpt-test',
        mensagem='Pergunta',
        enviar_teams=False,
    )
    conversa = criar_conversa(db_session, payload, correlation_id='corr-sem-msg')

    data = serializar_conversa(db_session, conversa, incluir_mensagens=False)

    assert data['id'] == conversa.id
    assert 'mensagens' not in data
