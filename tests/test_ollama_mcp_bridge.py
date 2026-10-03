from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "services" / "ollama-mcp-bridge" / "bridge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("ollama_mcp_bridge_core", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_module()


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_settings_reject_non_loopback_gateway() -> None:
    with pytest.raises(bridge.BridgeError, match="loopback"):
        bridge.load_settings(
            {
                "OLLAMA_MCP_GATEWAY_URL": "https://example.com:8008",
                "OLLAMA_MCP_ALLOWED_MODELS": "gemma4:31b-cloud",
            }
        )


def test_analyze_routes_only_allowlisted_model_to_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["headers"] = dict(request.header_items())
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return _Response(
            {
                "response": "analise ok",
                "model": "gemma4:31b-cloud",
                "requested_model": "gemma4:31b-cloud",
                "fallback_used": False,
                "latency_ms": 17,
            }
        )

    monkeypatch.setattr(bridge.urllib.request, "urlopen", fake_urlopen)
    settings = bridge.load_settings(
        {
            "OLLAMA_MCP_GATEWAY_URL": "http://127.0.0.1:8008",
            "OLLAMA_MCP_GATEWAY_API_KEY": "test-only",
            "OLLAMA_MCP_ALLOWED_MODELS": "gemma4:31b-cloud,gemma4:26b-q8-code",
            "OLLAMA_MCP_DEFAULT_MODEL": "gemma4:31b-cloud",
            "OLLAMA_MCP_FALLBACK_MODEL": "gemma4:26b-q8-code",
            "OLLAMA_MCP_TIMEOUT_SECONDS": "30",
        }
    )

    result = bridge.analyze(
        prompt="revise este diff",
        context="arquivo x",
        correlation_id="copilot-ollama-test-1",
        settings=settings,
    )

    assert observed["url"] == "http://127.0.0.1:8008/v1/chat"
    assert observed["payload"]["source"] == "github-copilot-ollama-mcp"
    assert observed["payload"]["fallback_model"] == "gemma4:26b-q8-code"
    assert observed["headers"]["X-correlation-id"] == "copilot-ollama-test-1"
    assert observed["headers"]["X-api-key"] == "test-only"
    assert result["response"] == "analise ok"
    assert result["provider"] == "ollama_gateway"
    assert result["fallback_used"] is False


def test_analyze_blocks_model_outside_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bridge.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("network must not be called"),
    )
    settings = bridge.load_settings(
        {
            "OLLAMA_MCP_ALLOWED_MODELS": "gemma4:31b-cloud,gemma4:26b-q8-code",
        }
    )
    with pytest.raises(bridge.BridgeError, match="not_allowlisted"):
        bridge.analyze(
            prompt="teste",
            model="modelo-nao-autorizado",
            settings=settings,
        )


def test_analyze_rejects_invalid_correlation_id_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bridge.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("network must not be called"),
    )
    with pytest.raises(bridge.BridgeError, match="invalid_correlation_id"):
        bridge.analyze(prompt="teste", correlation_id="valor com espaco")
