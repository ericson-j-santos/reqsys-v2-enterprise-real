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
