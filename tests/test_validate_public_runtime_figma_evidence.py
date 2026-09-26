from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_public_runtime.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_public_runtime", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


class FakeResponse:
    status = 200

    def __init__(self, payload: dict, headers: dict[str, str] | None = None):
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = headers or {"content-type": "application/json"}

    def read(self, _limit: int) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_optional_public_evidence_includes_figma_config_and_status() -> None:
    module = load_module()

    assert "/v1/integracoes/figma-github/config" in module.OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS
    assert "/v1/integracoes/figma-github/status" in module.OPTIONAL_PUBLIC_EVIDENCE_ENDPOINTS


def test_probe_extracts_correlation_id_from_envelope(monkeypatch) -> None:
    module = load_module()
    payload = {
        "success": True,
        "data": {"total": 0, "items": []},
        "errors": [],
        "meta": {"correlation_id": "corr-figma-123"},
    }
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))

    result = module.validar_endpoint(
        "https://reqsys-api.fly.dev",
        "/v1/integracoes/figma-github/status",
        1.0,
    )

    assert result.ok is True
    assert result.correlation_id == "corr-figma-123"


def test_probe_uses_header_correlation_as_fallback(monkeypatch) -> None:
    module = load_module()
    response = FakeResponse(
        {"success": True, "data": {"status": "ok"}, "errors": [], "meta": {}},
        {
            "content-type": "application/json",
            "x-correlation-id": "corr-header-456",
        },
    )
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: response)

    result = module.validar_endpoint("https://reqsys-api.fly.dev", "/health", 1.0)

    assert result.correlation_id == "corr-header-456"
