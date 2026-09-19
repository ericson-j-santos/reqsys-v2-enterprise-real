from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from reqsys_ollama_gateway.app import app
from reqsys_ollama_gateway.config import Settings
from reqsys_ollama_gateway.ollama_client import OllamaClient


def _settings() -> Settings:
    return Settings(
        env="dev",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_fallback_model="gemma4:26b-q8-code",
        ollama_fallback_timeout_seconds=180,
        auth_required=False,
        allowed_origins=("http://localhost:5173",),
        api_key="",
        ollama_timeout_seconds=60,
    )


def test_client_fallback_retorna_modelo_efetivo() -> None:
    fallback_response = MagicMock()
    fallback_response.raise_for_status = MagicMock()
    fallback_response.json.return_value = {"response": "FALLBACK_OK"}

    with patch("reqsys_ollama_gateway.ollama_client.httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__ = MagicMock(return_value=http)
        http.__exit__ = MagicMock(return_value=False)
        http.post.side_effect = [httpx.ConnectError("cloud offline"), fallback_response]
        client_cls.return_value = http

        response, latency_ms, model, fallback_used = OllamaClient(_settings()).generate_with_fallback(
            "gemma4:31b-cloud",
            "teste",
            "gemma4:26b-q8-code",
        )

    assert response == "FALLBACK_OK"
    assert latency_ms >= 0
    assert model == "gemma4:26b-q8-code"
    assert fallback_used is True
    assert client_cls.call_args_list[0].kwargs["timeout"] == 60
    assert client_cls.call_args_list[1].kwargs["timeout"] == 180


def test_chat_expoe_requested_model_e_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "false")
    client = TestClient(app)

    with patch(
        "reqsys_ollama_gateway.app.OllamaClient.generate_with_fallback",
        return_value=("FALLBACK_OK", 321, "gemma4:26b-q8-code", True),
    ):
        response = client.post(
            "/v1/chat",
            json={
                "model": "gemma4:31b-cloud",
                "fallback_model": "gemma4:26b-q8-code",
                "task_type": "code",
                "prompt": "teste",
                "contexto": "ctx",
                "entrada": "entrada",
                "correlation_id": "corr-fallback",
                "source": "reqsys-codex",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["requested_model"] == "gemma4:31b-cloud"
    assert data["model"] == "gemma4:26b-q8-code"
    assert data["fallback_used"] is True
