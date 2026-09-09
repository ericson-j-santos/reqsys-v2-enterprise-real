from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.secrets import get_secret

DEFAULT_ENDPOINTS = {
    'openai': 'https://api.openai.com/v1/chat/completions',
    'openai_embeddings': 'https://api.openai.com/v1/embeddings',
    'claude': 'https://api.anthropic.com/v1/messages',
    'groq': 'https://api.groq.com/openai/v1/chat/completions',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
    'gemini_embeddings': 'https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents',
}


class AIProviderRuntimeConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AIProviderRuntimeConfig:
    provider: str
    environment: str
    endpoint: str
    auth_mode: str
    secret: str
    secret_source: str


def _value(env: Mapping[str, str] | None, name: str) -> str:
    value = env.get(name) if env is not None else os.getenv(name)
    return str(value or '').strip()


def current_environment(env: Mapping[str, str] | None = None) -> str:
    raw = _value(env, 'ENVIRONMENT') or _value(env, 'APP_ENV') or 'dev'
    normalized = raw.strip().lower()
    aliases = {'development': 'dev', 'testing': 'test', 'stage': 'stg', 'staging': 'stg', 'production': 'prod'}
    return aliases.get(normalized, normalized)


def default_endpoint(provider: str) -> str:
    try:
        return DEFAULT_ENDPOINTS[provider]
    except KeyError as exc:
        raise AIProviderRuntimeConfigError(f'Endpoint padrão não definido para {provider}.') from exc


def resolve_endpoint(
    provider: str,
    *,
    env: Mapping[str, str] | None = None,
    endpoint_kind: str | None = None,
) -> str:
    environment = current_environment(env)
    key_provider = endpoint_kind or provider
    prefix = key_provider.upper()
    endpoint = (
        _value(env, f'AI_{environment.upper()}_{prefix}_ENDPOINT')
        or _value(env, f'AI_{prefix}_ENDPOINT')
        or default_endpoint(key_provider)
    )
    parsed = urlparse(endpoint.replace('{model}', 'model'))
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise AIProviderRuntimeConfigError(f'Endpoint inválido para {provider}.')

    hosts = (
        _value(env, f'AI_{environment.upper()}_ALLOWED_PROVIDER_HOSTS')
        or _value(env, 'AI_ALLOWED_PROVIDER_HOSTS')
    )
    if hosts:
        allowed = {item.strip().lower() for item in hosts.split(',') if item.strip()}
        if parsed.hostname and parsed.hostname.lower() not in allowed:
            raise AIProviderRuntimeConfigError(
                f'Host {parsed.hostname} não autorizado no ambiente {environment}.'
            )
    return endpoint


def resolve_secret(provider: str, *, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    env_name = f'AI_CONVERSATION_{provider.upper()}_API_KEY'
    vault_key = f'AI_CONVERSATION_{provider.upper()}_API_KEY'
    mapped = _value(env, env_name)
    if mapped:
        return mapped, 'mapping'

    prefer_vault = (_value(env, 'AI_CORPORATE_PREFER_VAULT') or 'true').lower() not in {'0', 'false', 'no'}
    secret = get_secret(env_name, '', vault_key=vault_key, prefer_vault=prefer_vault) or ''
    return secret, 'vault_or_env' if secret else 'absent'


def resolve_provider_config(
    provider: str,
    *,
    env: Mapping[str, str] | None = None,
) -> AIProviderRuntimeConfig:
    environment = current_environment(env)
    endpoint = resolve_endpoint(provider, env=env)
    auth_mode = (
        _value(env, f'AI_{environment.upper()}_{provider.upper()}_AUTH_MODE')
        or _value(env, f'AI_{provider.upper()}_AUTH_MODE')
        or ('bearer' if provider in {'openai', 'groq'} else 'api_key')
    ).lower()
    secret, source = resolve_secret(provider, env=env)
    if auth_mode not in {'bearer', 'api_key', 'none'}:
        raise AIProviderRuntimeConfigError(
            f'Modo de autenticação inválido para {provider}: {auth_mode}.'
        )
    if auth_mode != 'none' and not secret:
        raise AIProviderRuntimeConfigError(f'Segredo do provider {provider} não resolvido pelo cofre/configuração.')
    return AIProviderRuntimeConfig(
        provider=provider,
        environment=environment,
        endpoint=endpoint,
        auth_mode=auth_mode,
        secret=secret,
        secret_source=source,
    )
