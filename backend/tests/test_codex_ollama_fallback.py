from __future__ import annotations

import requests

from app.services.llm_provider import LLMGateway


def test_ollama_direct_fallback_usa_modelo_local_quando_cloud_falha() -> None:
    models: list[str] = []
    timeouts: list[int] = []

    def fake_post(url, payload, headers, timeout):
        models.append(payload["model"])
        timeouts.append(timeout)
        if len(models) == 1:
            raise requests.ConnectionError("cloud indisponivel")
        return {"response": "fallback ok"}

    gateway = LLMGateway(post_json=fake_post)
    response = gateway.gerar_ollama(
        base_url="http://127.0.0.1:11434",
        model="gemma4:31b-cloud",
        fallback_model="gemma4:26b-q8-code",
        fallback_timeout=180,
        prompt="teste",
    )

    assert response == "fallback ok"
    assert models == ["gemma4:31b-cloud", "gemma4:26b-q8-code"]
    assert timeouts == [45, 180]


def test_ollama_gateway_propaga_modelo_de_fallback() -> None:
    captured = {}

    def fake_post(url, payload, headers, timeout):
        captured.update(payload)
        return {"response": "ok"}

    gateway = LLMGateway(post_json=fake_post)
    response = gateway.gerar_ollama_gateway(
        base_url="http://127.0.0.1:8008",
        model="gemma4:31b-cloud",
        fallback_model="gemma4:26b-q8-code",
        prompt="teste",
        contexto="ctx",
        entrada="entrada",
        correlation_id="corr-fallback",
    )

    assert response == "ok"
    assert captured["model"] == "gemma4:31b-cloud"
    assert captured["fallback_model"] == "gemma4:26b-q8-code"
