from __future__ import annotations

import pytest

from app.services.ai_provider_router import AIProviderRouter, AIProviderRouterError, _safe_log_value


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def gerar_ollama_gateway(self, **kwargs):
        self.calls.append(('ollama_gateway', kwargs))
        return 'gateway ok'

    def gerar_ollama(self, **kwargs):
        self.calls.append(('ollama', kwargs))
        return 'ollama ok'

    def gerar_openai(self, **kwargs):
        self.calls.append(('openai', kwargs))
        return 'openai ok'

    def gerar_claude(self, **kwargs):
        self.calls.append(('claude', kwargs))
        return 'claude ok'

    def gerar_gemini(self, **kwargs):
        self.calls.append(('gemini', kwargs))
        return 'gemini ok'

    def gerar_groq(self, **kwargs):
        self.calls.append(('groq', kwargs))
        return 'groq ok'


def test_default_route_usa_ollama_gateway_e_propaga_fallback() -> None:
    gateway = FakeGateway()
    env = {
        'AI_DEFAULT_PROVIDER': 'ollama_gateway',
        'CODEX_OLLAMA_GATEWAY_URL': 'http://127.0.0.1:8008',
        'CODEX_OLLAMA_GATEWAY_MODEL': 'gemma4:31b-cloud',
        'CODEX_OLLAMA_FALLBACK_MODEL': 'gemma4:26b-q8-code',
    }
    result = AIProviderRouter(gateway=gateway, env=env).generate_text(
        prompt='teste',
        correlation_id='router-default-1',
    )

    assert result.provider == 'ollama_gateway'
    assert result.model == 'gemma4:31b-cloud'
    assert result.correlation_id == 'router-default-1'
    assert gateway.calls[0][0] == 'ollama_gateway'
    assert gateway.calls[0][1]['fallback_model'] == 'gemma4:26b-q8-code'


def test_provider_explicito_openai_continua_disponivel() -> None:
    gateway = FakeGateway()
    result = AIProviderRouter(gateway=gateway, env={}).generate_text(
        provider='openai',
        model='gpt-test',
        prompt='teste',
        system_prompt='sistema',
        correlation_id='router-openai-1',
        api_key='synthetic-test-key',
    )

    assert result.provider == 'openai'
    assert result.text == 'openai ok'
    assert gateway.calls[0][0] == 'openai'
    assert gateway.calls[0][1]['api_key'] == 'synthetic-test-key'
    assert gateway.calls[0][1]['model'] == 'gpt-test'
    assert 'endpoint' not in gateway.calls[0][1]


def test_ollama_direto_permanece_fallback_explicito() -> None:
    gateway = FakeGateway()
    env = {
        'CODEX_OLLAMA_BASE_URL': 'http://127.0.0.1:11434',
        'CODEX_OLLAMA_MODEL': 'local-code',
        'CODEX_OLLAMA_FALLBACK_MODEL': 'local-fallback',
    }
    result = AIProviderRouter(gateway=gateway, env=env).generate_text(
        provider='ollama',
        prompt='teste',
        correlation_id='router-local-1',
    )

    assert result.provider == 'ollama'
    assert gateway.calls[0][1]['fallback_model'] == 'local-fallback'


def test_gateway_sem_url_falha_fechado() -> None:
    gateway = FakeGateway()
    with pytest.raises(AIProviderRouterError, match='Gateway não configurado'):
        AIProviderRouter(gateway=gateway, env={'AI_DEFAULT_PROVIDER': 'ollama_gateway'}).generate_text(
            prompt='teste',
            correlation_id='router-negative-1',
        )


def test_provider_desconhecido_e_bloqueado() -> None:
    with pytest.raises(AIProviderRouterError, match='não suportado'):
        AIProviderRouter(gateway=FakeGateway(), env={}).generate_text(
            provider='provider-inventado',
            prompt='teste',
        )


def test_safe_log_value_remove_quebras_e_limita_tamanho() -> None:
    malicious = 'corr-ok\r\nforged-entry=admin' + ('x' * 300)
    sanitized = _safe_log_value(malicious)

    assert '\r' not in sanitized
    assert '\n' not in sanitized
    assert 'forged-entry=admin' in sanitized
    assert len(sanitized) == 200
