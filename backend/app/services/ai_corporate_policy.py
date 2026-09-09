from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

SUPPORTED_PROVIDERS = frozenset({'openai', 'claude', 'gemini', 'groq', 'ollama'})
SUPPORTED_DATA_CLASSIFICATIONS = frozenset({'public', 'internal', 'confidential', 'restricted'})
DEFAULT_LOCAL_PROVIDERS = frozenset({'ollama'})


class CorporateAIPolicyError(ValueError):
    """Bloqueio explícito de política corporativa de IA."""


@dataclass(frozen=True)
class CorporateAIPolicyDecision:
    allowed: bool
    requested_provider: str
    authorized_provider: str | None
    data_classification: str
    mode: str
    reason: str


def _env_value(env: Mapping[str, str] | None, name: str) -> str:
    value = env.get(name) if env is not None else os.getenv(name)
    return str(value or '').strip()


def _parse_csv(value: str) -> frozenset[str]:
    return frozenset(item.strip().lower() for item in value.split(',') if item.strip())


def policy_mode(env: Mapping[str, str] | None = None) -> str:
    mode = (_env_value(env, 'AI_CORPORATE_POLICY_MODE') or 'off').lower()
    if mode in {'off', 'disabled', 'legacy'}:
        return 'off'
    if mode == 'enforce':
        return mode
    raise CorporateAIPolicyError('AI_CORPORATE_POLICY_MODE inválido; use off ou enforce.')


def evaluate_provider_policy(
    *,
    provider: str,
    data_classification: str,
    env: Mapping[str, str] | None = None,
) -> CorporateAIPolicyDecision:
    provider_normalized = str(provider or '').strip().lower()
    classification_normalized = str(data_classification or '').strip().lower()

    if provider_normalized not in SUPPORTED_PROVIDERS:
        raise CorporateAIPolicyError(
            f'Provedor de IA não reconhecido pela política corporativa: {provider_normalized or "<vazio>"}.'
        )
    if classification_normalized not in SUPPORTED_DATA_CLASSIFICATIONS:
        raise CorporateAIPolicyError(
            'Classificação de informação inválida; use public, internal, confidential ou restricted.'
        )

    mode = policy_mode(env)
    if mode == 'off':
        return CorporateAIPolicyDecision(
            allowed=True,
            requested_provider=provider_normalized,
            authorized_provider=provider_normalized,
            data_classification=classification_normalized,
            mode=mode,
            reason='legacy_policy_mode_off',
        )

    class_key = f'AI_CORPORATE_{classification_normalized.upper()}_PROVIDERS'
    class_allowed = _parse_csv(_env_value(env, class_key))
    if not class_allowed:
        raise CorporateAIPolicyError(
            f'Nenhum provedor autorizado para {classification_normalized}; configure {class_key}.'
        )

    global_allowed = _parse_csv(_env_value(env, 'AI_CORPORATE_ALLOWED_PROVIDERS'))
    effective_allowed = class_allowed.intersection(global_allowed) if global_allowed else class_allowed

    if classification_normalized == 'restricted':
        configured_local = _parse_csv(_env_value(env, 'AI_CORPORATE_LOCAL_PROVIDERS'))
        local_providers = configured_local or DEFAULT_LOCAL_PROVIDERS
        if provider_normalized not in local_providers:
            raise CorporateAIPolicyError(
                'Dados restricted não podem atravessar a fronteira para um provedor externo.'
            )

    if provider_normalized not in effective_allowed:
        raise CorporateAIPolicyError(
            f'Provedor {provider_normalized} não autorizado para dados {classification_normalized}.'
        )

    return CorporateAIPolicyDecision(
        allowed=True,
        requested_provider=provider_normalized,
        authorized_provider=provider_normalized,
        data_classification=classification_normalized,
        mode=mode,
        reason='provider_explicitly_allowed_for_classification',
    )


def assert_provider_allowed(
    *,
    provider: str,
    data_classification: str,
    env: Mapping[str, str] | None = None,
) -> None:
    evaluate_provider_policy(
        provider=provider,
        data_classification=data_classification,
        env=env,
    )
