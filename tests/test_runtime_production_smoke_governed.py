from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest

from scripts import runtime_production_smoke_governed as smoke


class _FakeHeaders(dict):
    def get_content_type(self) -> str:
        return str(self.get("content-type", "application/json"))


class _FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b'{"data":{"status":"ok"}}') -> None:
        self.status = status
        self._body = body
        self.headers = _FakeHeaders({"content-type": "application/json"})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status


def test_normalize_base_url_remove_barra_final() -> None:
    assert smoke.normalize_base_url("https://reqsys-app.fly.dev/") == "https://reqsys-app.fly.dev"


def test_normalize_base_url_rejeita_url_invalida() -> None:
    with pytest.raises(ValueError):
        smoke.normalize_base_url("reqsys-app.fly.dev")


def test_check_endpoint_com_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke, "urlopen", lambda request, timeout: _FakeResponse())

    result = smoke.check_endpoint(
        "https://reqsys-app.fly.dev",
        "/api/runtime/health",
        purpose="runtime_health",
        expected_http=200,
        required=True,
        timeout_seconds=1,
        attempts=1,
        delay_seconds=0,
    )

    assert result.ok is True
    assert result.actual_http == 200
    assert result.envelope_status == "ok"


def test_check_endpoint_recupera_falha_transitoria(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def flaky_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("temporario")
        return _FakeResponse()

    monkeypatch.setattr(smoke, "urlopen", flaky_urlopen)
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)

    result = smoke.check_endpoint(
        "https://reqsys-app.fly.dev",
        "/health",
        purpose="basic_health",
        expected_http=200,
        required=True,
        timeout_seconds=1,
        attempts=2,
        delay_seconds=0,
    )

    assert result.ok is True
    assert calls["count"] == 2


def test_build_report_classifica_degraded_quando_required_falha() -> None:
    checks = [
        smoke.EndpointCheck("/health", "basic_health", True, 200, 200, True, 10),
        smoke.EndpointCheck("/api/runtime/readiness", "traffic_readiness", True, 200, None, False, 10, "timeout"),
        smoke.EndpointCheck("/runtime", "runtime_page", False, 200, 200, True, 10),
    ]

    report = smoke.build_report(
        checks,
        base_url="https://reqsys-app.fly.dev",
        repository="owner/repo",
        run_id="123",
    )

    assert report["status"] == "degraded"
    assert report["risk"] == "high"
    assert report["required_ok"] == 1
    assert report["required_total"] == 2


def test_main_gera_artifact_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(smoke, "urlopen", lambda request, timeout: _FakeResponse())
    output = tmp_path / "runtime-smoke.json"

    exit_code = smoke.main(
        [
            "--base-url",
            "https://reqsys-app.fly.dev",
            "--output",
            str(output),
            "--attempts",
            "1",
            "--delay-seconds",
            "0",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "healthy"
    assert payload["required_ok"] == payload["required_total"]


def test_run_smoke_required_e_optional_com_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke, "urlopen", lambda request, timeout: _FakeResponse())

    report = smoke.run_smoke(
        base_url="https://reqsys-app.fly.dev",
        timeout_seconds=1,
        attempts=1,
        delay_seconds=0,
        repository="owner/repo",
        run_id="123",
    )

    assert report["status"] == "healthy"
    assert report["required_success_percentual"] == 100.0
    assert report["required_total"] == len(smoke.REQUIRED_ENDPOINTS)
    assert report["optional_total"] == len(smoke.OPTIONAL_ENDPOINTS)
}
