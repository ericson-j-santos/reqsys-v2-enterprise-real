from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai_conversation import AIConversationCreateRequest
from app.services.ai_corporate_policy import (
    CorporateAIPolicyError,
    assert_provider_allowed,
    policy_mode,
)


def _payload(**overrides):
    data = {
        'provider': 'openai',
        'model': 'gpt-test',
        'mensagem': 'Analise este requisito.',
        'data_classification': 'internal',
        'enviar_teams': False,
    }
    data.update(overrides)
    return data


def test_policy_off_preserva_comportamento_legado():
    assert_provider_allowed(
        provider='openai',
        data_classification='confidential',
        env={'AI_CORPORATE_POLICY_MODE': 'off'},
    )


def test_policy_enforce_falha_fechado_sem_regra_da_classe():
    with pytest.raises(CorporateAIPolicyError, match='Nenhum provedor autorizado'):
        assert_provider_allowed(
            provider='openai',
            data_classification='internal',
            env={'AI_CORPORATE_POLICY_MODE': 'enforce'},
        )


def test_policy_enforce_permite_provider_explicitamente_autorizado():
    assert_provider_allowed(
        provider='openai',
        data_classification='internal',
        env={
            'AI_CORPORATE_POLICY_MODE': 'enforce',
            'AI_CORPORATE_INTERNAL_PROVIDERS': 'openai,ollama',
            'AI_CORPORATE_ALLOWED_PROVIDERS': 'openai,ollama',
        },
    )


def test_policy_global_allowlist_restringe_regra_da_classe():
    with pytest.raises(CorporateAIPolicyError, match='não autorizado'):
        assert_provider_allowed(
            provider='openai',
            data_classification='internal',
            env={
                'AI_CORPORATE_POLICY_MODE': 'enforce',
                'AI_CORPORATE_INTERNAL_PROVIDERS': 'openai,ollama',
                'AI_CORPORATE_ALLOWED_PROVIDERS': 'ollama',
            },
        )


def test_restricted_bloqueia_provider_externo_mesmo_se_configurado():
    with pytest.raises(CorporateAIPolicyError, match='não podem atravessar'):
        assert_provider_allowed(
            provider='openai',
            data_classification='restricted',
            env={
                'AI_CORPORATE_POLICY_MODE': 'enforce',
                'AI_CORPORATE_RESTRICTED_PROVIDERS': 'openai,ollama',
                'AI_CORPORATE_ALLOWED_PROVIDERS': 'openai,ollama',
            },
        )


def test_restricted_permite_ollama_quando_explicitamente_autorizado():
    assert_provider_allowed(
        provider='ollama',
        data_classification='restricted',
        env={
            'AI_CORPORATE_POLICY_MODE': 'enforce',
            'AI_CORPORATE_RESTRICTED_PROVIDERS': 'ollama',
            'AI_CORPORATE_ALLOWED_PROVIDERS': 'ollama',
        },
    )


def test_schema_aplica_gate_em_modo_enforce(monkeypatch):
    monkeypatch.setenv('AI_CORPORATE_POLICY_MODE', 'enforce')
    monkeypatch.delenv('AI_CORPORATE_INTERNAL_PROVIDERS', raising=False)

    with pytest.raises(ValidationError, match='Nenhum provedor autorizado'):
        AIConversationCreateRequest(**_payload())


def test_schema_aceita_classificacao_quando_regra_esta_configurada(monkeypatch):
    monkeypatch.setenv('AI_CORPORATE_POLICY_MODE', 'enforce')
    monkeypatch.setenv('AI_CORPORATE_INTERNAL_PROVIDERS', 'openai')
    monkeypatch.setenv('AI_CORPORATE_ALLOWED_PROVIDERS', 'openai')

    payload = AIConversationCreateRequest(**_payload())

    assert payload.data_classification == 'internal'
    assert payload.provider == 'openai'


def test_policy_mode_invalido_falha_fechado():
    with pytest.raises(CorporateAIPolicyError, match='inválido'):
        policy_mode({'AI_CORPORATE_POLICY_MODE': 'maybe'})
