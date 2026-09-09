from __future__ import annotations

import os
from collections.abc import Mapping

SUPPORTED_PROVIDERS = frozenset({'openai', 'claude', 'gemini', 'groq', 'ollama'})
SUPPORTED_DATA_CLASSIFICATIONS = frozenset({'public', 'internal', 'confidential', 'restricted'})
DEFAULT_LOCAL_PROVIDERS = frozenset({'ollama'})


class CorporateAIPolicyError(ValueError):
    """Bloqueio explícito de política corporativa de IA."""


def _env_value(env: Mapping[str, str] | None, name: str) -> str:
    value = env.get(name) if env is not None else os.getenv(name)
    return str(value or '').strip()


def _parse_csv(value: str) -> frozenset[str]:
    return frozenset(
        item.strip().lower()
        for item in value.split(',')
        if item.strip()
    )


def policy_mode(env: Mapping[str, str] | None = None) -> str:
    """Retorna `off` ou `enforce`; valores inválidos falham de forma segura."""
    mode = (_env_value(env, 'AI_CORPORATE_POLICY_MODE') or 'off').lower()
    if mode in {'off', 'disabled', 'legacy'}:
        return 'off'
    if mode == 'enforce':
        return mode
    raise CorporateAIPolicyError(
        'AI_CORPORATE_POLICY_MODE inválido; use off ou enforce.'
    )


def assert_provider_allowed(
    *,
    provider: str,
    data_classification: str,
    env: Mapping[str, str] | None = None,
) -> None:
    """Valida se um provedor pode processar a classificação informada.

    Em modo `off`, preserva o comportamento legado. Em `enforce`, a política é
    deny-by-default: a classe precisa declarar explicitamente seus provedores.
    Dados `restricted` possuem uma barreira adicional e só podem usar provedores
    considerados locais, independentemente de uma configuração permissiva por engano.
    """
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

    if policy_mode(env) == 'off':
        return

    class_key = f'AI_CORPORATE_{classification_normalized.upper()}_PROVIDERS'
    class_allowed = _parse_csv(_env_value(env, class_key))
    if not class_allowed:
        raise CorporateAIPolicyError(
            f'Nenhum provedor autorizado para {classification_normalized}; configure {class_key}.'
        )

    global_allowed = _parse_csv(_env_value(env, 'AI_CORPORATE_ALLOWED_PROVIDERS'))
    effective_allowed = class_allowed
    if global_allowed:
        effective_allowed = effective_allowed.intersection(global_allowed)

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
