from __future__ import annotations

import json

import httpx
import pytest

from app import microsoft_identity_e2e as e2e


def _configure_env(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-test")


def test_run_valida_power_platform_e_graph(monkeypatch):
    _configure_env(monkeypatch)
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            body = request.content.decode()
            token = "pp-token" if "api.powerplatform.com" in body else "graph-token"
            return httpx.Response(200, json={"access_token": token}, request=request)
        if request.url.host == "api.powerplatform.com":
            assert request.headers["Authorization"] == "Bearer pp-token"
            return httpx.Response(200, json={"value": [{"id": "env-1"}]}, request=request)
        if request.url.host == "graph.microsoft.com":
            assert request.headers["Authorization"] == "Bearer graph-token"
            return httpx.Response(200, json={"value": [{"id": "group-1"}]}, request=request)
        raise AssertionError(f"URL inesperada: {request.url}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(e2e.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))

    result = e2e.run()

    assert result["status"] == "PASS"
    assert [item["check"] for item in result["checks"]] == [
        "powerplatform_token",
        "powerplatform_environments",
        "graph_token",
        "graph_groups",
    ]
    assert result["checks"][1]["http_status"] == 200
    assert result["checks"][3]["items_observed"] == 1


def test_required_env_falha_sem_expor_segredo(monkeypatch):
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-super-sensivel")

    with pytest.raises(RuntimeError) as exc:
        e2e._required_env()

    assert "AZURE_TENANT_ID" in str(exc.value)
    assert "secret-super-sensivel" not in str(exc.value)


def test_main_sanitiza_falha_http(monkeypatch, capsys):
    _configure_env(monkeypatch)
    request = httpx.Request("GET", "https://graph.microsoft.com/v1.0/groups?$top=1")
    response = httpx.Response(403, json={"error": {"message": "detalhe sensível"}}, request=request)

    def fail_run():
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(e2e, "run", fail_run)

    assert e2e.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "FAIL",
        "stage": "microsoft_http",
        "http_status": 403,
        "request_url": "https://graph.microsoft.com/v1.0/groups",
    }
