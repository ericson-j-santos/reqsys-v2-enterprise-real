from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, call_with_retry
from app.services.ai_provider_config import default_endpoint

PostJsonFn = Callable[[str, dict[str, Any], dict[str, str] | None, int], dict[str, Any]]

LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF_SECONDS = 0.5
LLM_CIRCUIT_FAILURE_THRESHOLD = 3
LLM_CIRCUIT_COOLDOWN_SECONDS = 60

_circuits: dict[str, CircuitBreaker] = {}


def _circuit_for(url: str) -> CircuitBreaker:
    host = urlparse(url).netloc or 'default'
    if host not in _circuits:
        _circuits[host] = CircuitBreaker(
            name=f'llm_{host}',
            failure_threshold=LLM_CIRCUIT_FAILURE_THRESHOLD,
            cooldown_seconds=LLM_CIRCUIT_COOLDOWN_SECONDS,
        )
    return _circuits[host]


def reset_circuit_breakers() -> None:
    for circuit in _circuits.values():
        circuit.reset()


def _do_post(url: str, payload: dict[str, Any], headers: dict[str, str] | None, timeout: int) -> dict[str, Any]:
    resposta = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    resposta.raise_for_status()
    return resposta.json()


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 45,
    *,
    sleep=time.sleep,
    max_retries: int = LLM_MAX_RETRIES,
) -> dict[str, Any]:
    try:
        return call_with_retry(
            lambda: _do_post(url, payload, headers, timeout),
            max_retries=max_retries,
            backoff_seconds=LLM_RETRY_BACKOFF_SECONDS,
            retry_on=(requests.ConnectionError, requests.Timeout),
            sleep=sleep,
            circuit=_circuit_for(url),
        )
    except CircuitBreakerOpenError as exc:
        raise requests.ConnectionError(str(exc)) from exc


def extrair_resposta_textual(data: dict[str, Any]) -> str:
    candidatos = [data.get('response'), data.get('resposta'), data.get('resultado'), data.get('answer'), data.get('content')]
    envelope = data.get('data')
    if isinstance(envelope, dict):
        candidatos.extend([
            envelope.get('response'), envelope.get('resposta'), envelope.get('resultado'),
            envelope.get('answer'), envelope.get('content'),
        ])
    for candidato in candidatos:
        if candidato:
            return str(candidato)
    raise RuntimeError('Resposta do provider sem conteudo utilizavel')


def extrair_resposta_gemini(data: dict[str, Any]) -> str:
    output_text = data.get('output_text')
    if output_text:
        return str(output_text)
    text = data.get('text')
    if text:
        return str(text)
    candidates = data.get('candidates') or []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content') or {}
        parts = content.get('parts') or []
        textos = [str(part.get('text') or '') for part in parts if isinstance(part, dict) and part.get('text')]
        if textos:
            return '\n'.join(textos)
    raise RuntimeError('Resposta do Gemini sem conteudo utilizavel')


def _auth_headers(api_key: str, auth_mode: str, *, provider: str) -> dict[str, str]:
    headers = {'Content-Type': 'application/json'}
    if auth_mode == 'none':
        return headers
    if auth_mode == 'bearer':
        headers['Authorization'] = f'Bearer {api_key}'
        return headers
    if auth_mode == 'api_key':
        if provider == 'claude':
            headers['x-api-key'] = api_key
            headers['anthropic-version'] = '2023-06-01'
        elif provider == 'gemini':
            headers['x-goog-api-key'] = api_key
        elif provider == 'openai':
            headers['api-key'] = api_key
        else:
            headers['X-API-Key'] = api_key
        return headers
    raise RuntimeError(f'Modo de autenticação não suportado: {auth_mode}')


class LLMGateway:
    """Porta única de LLM. Endpoints e autenticação podem ser injetados pelo ambiente corporativo."""

    def __init__(self, post_json: PostJsonFn = _post_json) -> None:
        self._post_json = post_json

    def gerar_ollama(self, *, base_url: str, model: str, prompt: str, timeout: int = 45) -> str:
        base = (base_url or 'http://localhost:11434').rstrip('/')
        payload = {'model': model, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.1}}
        data = self._post_json(f'{base}/api/generate', payload, headers=None, timeout=timeout)
        return str(data.get('response') or '')

    def gerar_ollama_gateway(
        self, *, base_url: str, model: str, prompt: str, contexto: str, entrada: str,
        correlation_id: str, api_key: str = '', timeout: int = 60,
    ) -> str:
        if not base_url:
            raise RuntimeError('CODEX_OLLAMA_GATEWAY_URL ausente')
        base = base_url.rstrip('/')
        payload = {
            'model': model, 'task_type': 'code', 'prompt': prompt, 'contexto': contexto,
            'entrada': entrada, 'correlation_id': correlation_id, 'source': 'reqsys-codex-local-online',
        }
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['X-API-Key'] = api_key
        data = self._post_json(f'{base}/v1/chat', payload, headers=headers, timeout=max(1, int(timeout)))
        return extrair_resposta_textual(data)

    def gerar_openai(
        self, *, api_key: str, model: str, prompt: str, system_prompt: str,
        timeout: int = 45, endpoint: str | None = None, auth_mode: str = 'bearer',
    ) -> str:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('CODEX_OPENAI_KEY ausente')
        payload = {
            'model': model,
            'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}],
            'temperature': 0.1,
        }
        headers = _auth_headers(api_key, auth_mode, provider='openai')
        data = self._post_json(endpoint or default_endpoint('openai'), payload, headers=headers, timeout=timeout)
        return str(data['choices'][0]['message']['content'])

    def gerar_embeddings_openai(
        self, *, api_key: str, model: str, textos: list[str], timeout: int = 45,
        endpoint: str | None = None, auth_mode: str = 'bearer',
    ) -> list[list[float]]:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('REQSYS_RAG_EMBEDDING_API_KEY ausente')
        payload = {'model': model, 'input': textos}
        headers = _auth_headers(api_key, auth_mode, provider='openai')
        data = self._post_json(endpoint or default_endpoint('openai_embeddings'), payload, headers=headers, timeout=timeout)
        itens = sorted(data['data'], key=lambda item: item['index'])
        return [[float(valor) for valor in item['embedding']] for item in itens]

    def gerar_claude(
        self, *, api_key: str, model: str, prompt: str, system_prompt: str,
        timeout: int = 45, endpoint: str | None = None, auth_mode: str = 'api_key',
    ) -> str:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('CODEX_CLAUDE_KEY ausente')
        payload = {
            'model': model, 'max_tokens': 1600, 'temperature': 0.1,
            'system': system_prompt, 'messages': [{'role': 'user', 'content': prompt}],
        }
        headers = _auth_headers(api_key, auth_mode, provider='claude')
        data = self._post_json(endpoint or default_endpoint('claude'), payload, headers=headers, timeout=timeout)
        blocos = data.get('content') or []
        return '\n'.join(str(item.get('text') or '') for item in blocos if isinstance(item, dict))

    def gerar_groq(
        self, *, api_key: str, model: str, prompt: str, system_prompt: str | None = None,
        timeout: int = 45, endpoint: str | None = None, auth_mode: str = 'bearer',
    ) -> str:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('GROQ_API_KEY ausente')
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        payload = {'model': model, 'messages': messages, 'temperature': 0.1}
        headers = _auth_headers(api_key, auth_mode, provider='groq')
        data = self._post_json(endpoint or default_endpoint('groq'), payload, headers=headers, timeout=timeout)
        return str(data['choices'][0]['message']['content'])

    def gerar_gemini(
        self, *, api_key: str, model: str, prompt: str, system_prompt: str | None = None,
        timeout: int = 45, endpoint: str | None = None, auth_mode: str = 'api_key',
    ) -> str:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('GEMINI_API_KEY ausente')
        payload: dict[str, Any] = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.1},
        }
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
        headers = _auth_headers(api_key, auth_mode, provider='gemini')
        url = (endpoint or default_endpoint('gemini')).replace('{model}', model)
        data = self._post_json(url, payload, headers=headers, timeout=timeout)
        return extrair_resposta_gemini(data)

    def gerar_embeddings_gemini(
        self, *, api_key: str, model: str, textos: list[str], timeout: int = 45,
        endpoint: str | None = None, auth_mode: str = 'api_key',
    ) -> list[list[float]]:
        if auth_mode != 'none' and not api_key:
            raise RuntimeError('GEMINI_API_KEY ausente')
        modelo_normalizado = model if model.startswith('models/') else f'models/{model}'
        payload = {
            'requests': [
                {'model': modelo_normalizado, 'content': {'parts': [{'text': texto}]}}
                for texto in textos
            ]
        }
        headers = _auth_headers(api_key, auth_mode, provider='gemini')
        url = (endpoint or default_endpoint('gemini_embeddings')).replace('{model}', modelo_normalizado)
        data = self._post_json(url, payload, headers=headers, timeout=timeout)
        return [[float(valor) for valor in item['values']] for item in data['embeddings']]
