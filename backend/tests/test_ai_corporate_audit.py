from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai_conversation import (
    AIProviderConfigurationError,
    _classification_lock,
    _validar_politica_persistida,
)
from app.services.ai_corporate_policy import evaluate_provider_policy


def test_decisao_expoe_provedor_classificacao_e_motivo() -> None:
    decision = evaluate_provider_policy(
        provider='openai',
        data_classification='internal',
        env={'AI_CORPORATE_POLICY_MODE': 'off'},
    )
    assert decision.allowed is True
    assert decision.requested_provider == 'openai'
    assert decision.authorized_provider == 'openai'
    assert decision.data_classification == 'internal'
    assert decision.reason == 'legacy_policy_mode_off'


def test_trava_da_classificacao_e_deterministica() -> None:
    first = _classification_lock('conv-1', 'confidential')
    second = _classification_lock('conv-1', 'confidential')
    assert first == second
    assert len(first) == 64
    assert first != _classification_lock('conv-1', 'restricted')


def test_alteracao_silenciosa_da_classificacao_e_bloqueada() -> None:
    conversa = SimpleNamespace(
        id='conv-1',
        provider='ollama',
        requested_provider='ollama',
        authorized_provider='ollama',
        data_classification='restricted',
        classification_lock_sha256=_classification_lock('conv-1', 'internal'),
        policy_decision='allowed',
        policy_reason='original',
        policy_correlation_id='corr-1',
        policy_mode='off',
    )

    with pytest.raises(AIProviderConfigurationError, match='trava de integridade'):
        _validar_politica_persistida(
            conversa,
            correlation_id='corr-2',
            env={'AI_CORPORATE_POLICY_MODE': 'off'},
        )


def test_defesa_em_profundidade_reavalia_restricted() -> None:
    conversa = SimpleNamespace(
        id='conv-2',
        provider='openai',
        requested_provider='openai',
        authorized_provider='openai',
        data_classification='restricted',
        classification_lock_sha256=_classification_lock('conv-2', 'restricted'),
        policy_decision='allowed',
        policy_reason='original',
        policy_correlation_id='corr-1',
        policy_mode='off',
    )
    env = {
        'AI_CORPORATE_POLICY_MODE': 'enforce',
        'AI_CORPORATE_RESTRICTED_PROVIDERS': 'openai,ollama',
        'AI_CORPORATE_ALLOWED_PROVIDERS': 'openai,ollama',
        'AI_CORPORATE_LOCAL_PROVIDERS': 'ollama',
    }

    with pytest.raises(AIProviderConfigurationError, match='não podem atravessar'):
        _validar_politica_persistida(conversa, correlation_id='corr-2', env=env)

    assert conversa.policy_decision == 'blocked'
    assert conversa.policy_correlation_id == 'corr-2'
