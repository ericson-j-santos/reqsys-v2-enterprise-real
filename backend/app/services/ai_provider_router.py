from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from app.core.config import settings
from app.services.ai_provider_config import (
    AIProviderRuntimeConfigError,
    resolve_provider_config,
)
from app.services.llm_provider import LLMGateway

logger = logging.getLogger('reqsys.ai_provider_router')

SUPPORTED_TEXT_PROVIDERS = frozenset({
    'ollama_gateway',
    'ollama',
    'openai',
    'claude',
    'gemini',
    'groq',
})
DEFAULT_TEXT_PROVIDER = 'ollama_gateway'


class AIProviderRouterError(RuntimeError):
    """Falha de roteamento/configuração de provider de IA."""


@dataclass(frozen=True)
class AIRouteResult:
    text: str
    requested_provider: str
    provider: str
    model: str
    correlation_id: str


def _value(env: Mapping[str, str] | None, *names: str) -> str:
    for name in names:
        value = env.get(name) if env is not None else os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return ''


def _safe_log_value(value: object, *, max_length: int = 200) -> str:
    """Remove delimitadores capazes de forjar novas linhas de log."""
    return str(value).replace('\r', ' ').replace('\n', ' ')[:max_length]


class AIProviderRouter:
    """Roteador único de providers textuais do ReqSys.

    A rota padrão é ollama_gateway. O roteador centraliza seleção, configuração,
    fallback local e rastreabilidade; LLMGateway permanece a única porta HTTP.
    """

    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._gateway = gateway or LLMGateway()
        self._env = env

    def _default_provider(self) -> str:
        provider = (
            _value(self._env, 'AI_DEFAULT_PROVIDER')
            or getattr(settings, 'ai_default_provider', '')
            or DEFAULT_TEXT_PROVIDER
        ).strip().lower()
        if provider not in SUPPORTED_TEXT_PROVIDERS:
            raise AIProviderRouterError(f'AI_DEFAULT_PROVIDER não suportado: {provider}.')
        return provider

    def resolve_provider(self, provider: str | None) -> str:
        normalized = str(provider or '').strip().lower() or self._default_provider()
        if normalized not in SUPPORTED_TEXT_PROVIDERS:
            raise AIProviderRouterError(f'Provedor não suportado pelo AI Provider Router: {normalized}.')
        return normalized

    def _ollama_gateway_config(self, model: str) -> tuple[str, str, str, str, int]:
        base_url = (
            _value(
                self._env,
                'AI_OLLAMA_GATEWAY_URL',
                'AI_CONVERSATION_OLLAMA_GATEWAY_URL',
                'CODEX_OLLAMA_GATEWAY_URL',
            )
            or settings.codex_ollama_gateway_url
        )
        if not base_url:
            raise AIProviderRouterError('Ollama Gateway não configurado: CODEX_OLLAMA_GATEWAY_URL ausente.')
        effective_model = (
            str(model or '').strip()
            or _value(self._env, 'AI_OLLAMA_GATEWAY_MODEL', 'CODEX_OLLAMA_GATEWAY_MODEL', 'CODEX_OLLAMA_MODEL')
            or settings.codex_ollama_gateway_model
            or settings.codex_ollama_model
        )
        if not effective_model:
            raise AIProviderRouterError('Modelo do Ollama Gateway não configurado.')
        fallback_model = (
            _value(self._env, 'AI_OLLAMA_FALLBACK_MODEL', 'CODEX_OLLAMA_FALLBACK_MODEL')
            or settings.codex_ollama_fallback_model
        )
        api_key = (
            _value(self._env, 'AI_OLLAMA_GATEWAY_API_KEY', 'CODEX_OLLAMA_GATEWAY_API_KEY')
            or settings.codex_ollama_gateway_api_key
        )
        timeout = int(
            _value(self._env, 'AI_OLLAMA_GATEWAY_TIMEOUT_SECONDS', 'CODEX_OLLAMA_GATEWAY_TIMEOUT_SECONDS')
            or settings.codex_ollama_gateway_timeout_seconds
        )
        return base_url, effective_model, fallback_model, api_key, max(1, timeout)

    def _ollama_config(self, model: str) -> tuple[str, str, str, int]:
        base_url = (
            _value(self._env, 'AI_OLLAMA_BASE_URL', 'AI_CONVERSATION_OLLAMA_BASE_URL', 'CODEX_OLLAMA_BASE_URL', 'OLLAMA_BASE_URL')
            or settings.codex_ollama_base_url
        )
        if not base_url:
            raise AIProviderRouterError('Ollama não configurado.')
        effective_model = (
            str(model or '').strip()
            or _value(self._env, 'AI_OLLAMA_MODEL', 'CODEX_OLLAMA_MODEL', 'OLLAMA_MODEL')
            or settings.codex_ollama_model
        )
        if not effective_model:
            raise AIProviderRouterError('Modelo Ollama não configurado.')
        fallback_model = (
            _value(self._env, 'AI_OLLAMA_FALLBACK_MODEL', 'CODEX_OLLAMA_FALLBACK_MODEL')
            or settings.codex_ollama_fallback_model
        )
        fallback_timeout = int(
            _value(self._env, 'AI_OLLAMA_FALLBACK_TIMEOUT_SECONDS', 'CODEX_OLLAMA_FALLBACK_TIMEOUT_SECONDS')
            or settings.codex_ollama_fallback_timeout_seconds
        )
        return base_url, effective_model, fallback_model, max(1, fallback_timeout)

    def check_configured(self, provider: str | None) -> None:
        resolved = self.resolve_provider(provider)
        if resolved == 'ollama_gateway':
            self._ollama_gateway_config('')
            return
        if resolved == 'ollama':
            self._ollama_config('')
            return
        try:
            resolve_provider_config(resolved, env=self._env)
        except AIProviderRuntimeConfigError as exc:
            raise AIProviderRouterError(str(exc)) from None

    def generate_text(
        self,
        *,
        provider: str | None = None,
        model: str = '',
        prompt: str,
        system_prompt: str = '',
        correlation_id: str = '',
        context: str = '',
        input_text: str = '',
        timeout: int = 60,
        api_key: str | None = None,
        endpoint: str | None = None,
        auth_mode: str | None = None,
    ) -> AIRouteResult:
        resolved = self.resolve_provider(provider)
        correlation = str(correlation_id or '').strip() or 'ai-router-untracked'
        requested_provider = str(provider or '').strip().lower() or resolved
        timeout = max(1, int(timeout))

        if resolved == 'ollama_gateway':
            base_url, effective_model, fallback_model, configured_key, configured_timeout = self._ollama_gateway_config(model)
            text = self._gateway.gerar_ollama_gateway(
                base_url=base_url,
                model=effective_model,
                prompt=prompt,
                contexto=context,
                entrada=input_text,
                correlation_id=correlation,
                api_key=configured_key if api_key is None else api_key,
                timeout=timeout if timeout != 60 else configured_timeout,
                fallback_model=fallback_model,
            )
        elif resolved == 'ollama':
            base_url, effective_model, fallback_model, fallback_timeout = self._ollama_config(model)
            text = self._gateway.gerar_ollama(
                base_url=base_url,
                model=effective_model,
                prompt=f'{system_prompt}\n\n{prompt}' if system_prompt else prompt,
                timeout=timeout,
                fallback_model=fallback_model,
                fallback_timeout=fallback_timeout,
            )
        else:
            effective_model = str(model or '').strip()
            if not effective_model:
                raise AIProviderRouterError(f'Modelo não configurado para {resolved}.')
            method = getattr(self._gateway, f'gerar_{resolved}')

            # Compatibilidade: consumidores legados que já resolvem a credencial
            # continuam usando a assinatura mínima do LLMGateway. Assim preservamos
            # semântica de exceções/model fallback e mantemos o router apenas como
            # camada de seleção/rastreabilidade.
            if api_key is not None and endpoint is None and auth_mode is None:
                text = method(
                    api_key=str(api_key or ''),
                    model=effective_model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            else:
                try:
                    runtime = resolve_provider_config(resolved, env=self._env)
                    effective_key = runtime.secret if api_key is None else str(api_key or '')
                    effective_endpoint = endpoint or runtime.endpoint
                    effective_auth_mode = auth_mode or runtime.auth_mode
                except AIProviderRuntimeConfigError as exc:
                    raise AIProviderRouterError(str(exc)) from None
                text = method(
                    api_key=effective_key,
                    model=effective_model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    timeout=timeout,
                    endpoint=effective_endpoint,
                    auth_mode=effective_auth_mode,
                )

        normalized = str(text or '').strip()
        if not normalized:
            raise AIProviderRouterError(f'Provider {resolved} retornou resposta vazia.')

        logger.info(
            'ai_provider_route correlation_id=%s requested_provider=%s provider=%s model=%s',
            _safe_log_value(correlation),
            _safe_log_value(requested_provider),
            _safe_log_value(resolved),
            _safe_log_value(effective_model),
        )
        return AIRouteResult(
            text=normalized,
            requested_provider=requested_provider,
            provider=resolved,
            model=effective_model,
            correlation_id=correlation,
        )
