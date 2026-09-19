from __future__ import annotations

import time
from typing import Any

import httpx

from .config import Settings


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.ollama_base_url.rstrip('/')

    def generate(self, model: str, prompt: str) -> tuple[str, int]:
        payload: dict[str, Any] = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': 0.1},
        }
        inicio = time.perf_counter()
        with httpx.Client(timeout=self._settings.ollama_timeout_seconds) as client:
            resposta = client.post(f'{self._base_url}/api/generate', json=payload)
            resposta.raise_for_status()
            data = resposta.json()
        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        return str(data.get('response') or ''), latencia_ms


    def generate_with_fallback(
        self,
        model: str,
        prompt: str,
        fallback_model: str = '',
    ) -> tuple[str, int, str, bool]:
        started = time.perf_counter()
        try:
            response, latency_ms = self.generate(model, prompt)
            return response, latency_ms, model, False
        except httpx.HTTPError:
            fallback = (fallback_model or '').strip()
            if not fallback or fallback == model:
                raise
            response, _ = self.generate(fallback, prompt)
            total_ms = int((time.perf_counter() - started) * 1000)
            return response, total_ms, fallback, True
