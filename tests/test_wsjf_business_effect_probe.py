from __future__ import annotations

import httpx
import pytest

from scripts import wsjf_business_effect_probe as probe


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://graph.microsoft.com/v1.0/test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


def test_retry_locked_repete_423_e_conclui(monkeypatch):
    chamadas = {"total": 0}
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)

    def operacao():
        chamadas["total"] += 1
        if chamadas["total"] < 3:
            raise _http_error(423)
        return "ok"

    assert probe._retry_locked(operacao, attempts=4, delay_seconds=0) == "ok"
    assert chamadas["total"] == 3


def test_retry_locked_nao_mascara_erro_nao_transitorio(monkeypatch):
    chamadas = {"total": 0}
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)

    def operacao():
        chamadas["total"] += 1
        raise _http_error(404)

    with pytest.raises(httpx.HTTPStatusError):
        probe._retry_locked(operacao, attempts=4, delay_seconds=0)

    assert chamadas["total"] == 1


def test_retry_locked_falha_apos_limite(monkeypatch):
    chamadas = {"total": 0}
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)

    def operacao():
        chamadas["total"] += 1
        raise _http_error(423)

    with pytest.raises(httpx.HTTPStatusError):
        probe._retry_locked(operacao, attempts=3, delay_seconds=0)

    assert chamadas["total"] == 3


def test_retry_locked_usa_politica_configuravel_por_ambiente(monkeypatch):
    chamadas = {"total": 0}
    monkeypatch.setenv(probe.LOCK_RETRY_ATTEMPTS_ENV, "4")
    monkeypatch.setenv(probe.LOCK_RETRY_DELAY_SECONDS_ENV, "0")
    monkeypatch.setattr(probe.time, "sleep", lambda _seconds: None)

    def operacao():
        chamadas["total"] += 1
        if chamadas["total"] < 4:
            raise _http_error(423)
        return "ok"

    assert probe._retry_locked(operacao) == "ok"
    assert chamadas["total"] == 4


def test_retry_locked_rejeita_politica_fora_dos_limites(monkeypatch):
    monkeypatch.setenv(probe.LOCK_RETRY_ATTEMPTS_ENV, "0")

    with pytest.raises(ValueError, match=probe.LOCK_RETRY_ATTEMPTS_ENV):
        probe._retry_locked(lambda: "ok")
