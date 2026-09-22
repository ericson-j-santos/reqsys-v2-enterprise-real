from __future__ import annotations

import pytest

from app.services.ai_corporate_policy import CorporateAIPolicyError, evaluate_provider_policy
from app.services.ai_provider_config import (
    AIProviderRuntimeConfigError,
    default_endpoint,
    resolve_endpoint,
    resolve_provider_config,
)
from app.services.llm_provider import LLMGateway


def test_endpoint_especifico_de_prod_prevalece() -> None:
    env = {
        'ENVIRONMENT': 'prod',
        'AI_PROD_OPENAI_ENDPOINT': 'https://ai-gateway.corp.example/v1/chat',
        'AI_PROD_ALLOWED_PROVIDER_HOSTS': 'ai-gateway.corp.example',
    }
    assert resolve_endpoint('openai', env=env) == 'https://ai-gateway.corp.example/v1/chat'


def test_host_fora_da_allowlist_e_bloqueado() -> None:
    env = {
        'ENVIRONMENT': 'prod',
        'AI_PROD_OPENAI_ENDPOINT': 'https://example.invalid/v1/chat',
        'AI_PROD_ALLOWED_PROVIDER_HOSTS': 'ai-gateway.corp.example',
    }
    with pytest.raises(AIProviderRuntimeConfigError, match='não autorizado'):
        resolve_endpoint('openai', env=env)


def test_endpoint_padrao_inexistente_e_rejeitado() -> None:
    with pytest.raises(AIProviderRuntimeConfigError, match='Endpoint padrão não definido'):
        default_endpoint('provider-inexistente')


def test_endpoint_invalido_e_rejeitado() -> None:
    env = {
        'ENVIRONMENT': 'dev',
        'AI_DEV_OPENAI_ENDPOINT': 'endpoint-sem-scheme',
    }
    with pytest.raises(AIProviderRuntimeConfigError, match='Endpoint inválido'):
        resolve_endpoint('openai', env=env)


def test_segredo_legado_mapeado_permanece_compativel() -> None:
    config = resolve_provider_config(
        'openai',
        env={
            'ENVIRONMENT': 'dev',
            'CODEX_OPENAI_KEY': 'legacy-secret',
        },
    )

    assert config.secret == 'legacy-secret'
    assert config.secret_source == 'mapping:CODEX_OPENAI_KEY'


def test_provider_e_limitado_por_ambiente() -> None:
    env = {
        'ENVIRONMENT': 'prod',
        'AI_CORPORATE_POLICY_MODE': 'enforce',
        'AI_CORPORATE_INTERNAL_PROVIDERS': 'openai,ollama',
        'AI_CORPORATE_ALLOWED_PROVIDERS': 'openai,ollama',
        'AI_PROD_ALLOWED_PROVIDERS': 'ollama',
    }
    with pytest.raises(CorporateAIPolicyError, match='ambiente prod'):
        evaluate_provider_policy(provider='openai', data_classification='internal', env=env)


def test_config_azure_openai_via_endpoint_completo_e_api_key() -> None:
    env = {
        'ENVIRONMENT': 'test',
        'AI_TEST_OPENAI_ENDPOINT': 'https://tenant.openai.azure.com/openai/deployments/gpt/chat/completions?api-version=2024-10-21',
        'AI_TEST_OPENAI_AUTH_MODE': 'api_key',
        'AI_CONVERSATION_OPENAI_API_KEY': 'segredo-fake',
    }
    config = resolve_provider_config('openai', env=env)
    assert config.auth_mode == 'api_key'
    assert config.secret == 'segredo-fake'
    assert 'openai.azure.com' in config.endpoint


def test_gateway_openai_api_key_usa_header_azure() -> None:
    captured = {}

    def fake_post(url, payload, headers, timeout):
        captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {'choices': [{'message': {'content': 'ok'}}]}

    gateway = LLMGateway(post_json=fake_post)
    response = gateway.gerar_openai(
        api_key='secret',
        model='deployment-model',
        prompt='p',
        system_prompt='s',
        endpoint='https://tenant.openai.azure.com/openai/deployments/gpt/chat/completions?api-version=2024-10-21',
        auth_mode='api_key',
    )
    assert response == 'ok'
    assert captured['headers']['api-key'] == 'secret'
    assert 'Authorization' not in captured['headers']


def test_gateway_proxy_sem_segredo_quando_auth_none() -> None:
    captured = {}

    def fake_post(url, payload, headers, timeout):
        captured['headers'] = headers
        return {'choices': [{'message': {'content': 'proxy-ok'}}]}

    response = LLMGateway(post_json=fake_post).gerar_openai(
        api_key='',
        model='corporate-model',
        prompt='p',
        system_prompt='s',
        endpoint='https://ai-proxy.corp.example/v1/chat',
        auth_mode='none',
    )
    assert response == 'proxy-ok'
    assert captured['headers'] == {'Content-Type': 'application/json'}
