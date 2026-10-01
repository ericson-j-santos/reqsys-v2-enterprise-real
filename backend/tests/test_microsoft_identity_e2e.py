from __future__ import annotations

import json

import httpx
import pytest

from app import microsoft_identity_e2e as e2e


def _configure_env(monkeypatch):
    monkeypatch.setenv("POWER_PLATFORM_TENANT_ID", "tenant-power")
    monkeypatch.setenv("POWER_PLATFORM_CLIENT_ID", "client-power")
    monkeypatch.setenv("POWER_PLATFORM_CLIENT_SECRET", "secret-power")
    monkeypatch.setenv("DATAVERSE_TENANT_ID", "tenant-dataverse")
    monkeypatch.setenv("DATAVERSE_CLIENT_ID", "client-dataverse")
    monkeypatch.setenv("DATAVERSE_CLIENT_SECRET", "secret-dataverse")
    monkeypatch.setenv("DATAVERSE_ENVIRONMENT_URL", "https://org-test.crm2.dynamics.com")


def test_run_valida_power_platform_e_dataverse(monkeypatch):
    _configure_env(monkeypatch)
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            body = request.content.decode()
            token = "pp-token" if "api.powerplatform.com" in body else "dataverse-token"
            return httpx.Response(200, json={"access_token": token}, request=request)
        if request.url.host == "api.powerplatform.com":
            assert request.headers["Authorization"] == "Bearer pp-token"
            return httpx.Response(200, json={"value": [{"id": "env-1"}]}, request=request)
        if request.url.host == "org-test.crm2.dynamics.com":
            assert request.headers["Authorization"] == "Bearer dataverse-token"
            return httpx.Response(200, json={"UserId": "user-1"}, request=request)
        raise AssertionError(f"URL inesperada: {request.url}")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(e2e.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))

    result = e2e.run()

    assert result["status"] == "PASS"
    assert [item["check"] for item in result["checks"]] == [
        "powerplatform_token",
        "powerplatform_environments",
        "dataverse_token",
        "dataverse_whoami",
    ]
    assert result["checks"][1]["http_status"] == 200
    assert result["checks"][3]["items_observed"] == 0


def test_required_env_falha_sem_expor_segredo(monkeypatch):
    _configure_env(monkeypatch)
    monkeypatch.delenv("DATAVERSE_TENANT_ID", raising=False)
    monkeypatch.setenv("DATAVERSE_CLIENT_SECRET", "secret-super-sensivel")

    with pytest.raises(RuntimeError) as exc:
        e2e._required_env()

    assert "DATAVERSE_TENANT_ID" in str(exc.value)
    assert "secret-super-sensivel" not in str(exc.value)


def test_main_sanitiza_falha_http(monkeypatch, capsys):
    _configure_env(monkeypatch)
    request = httpx.Request("GET", "https://api.powerplatform.com/environmentmanagement/environments?api-version=2024-10-01")
    response = httpx.Response(403, json={"error": {"message": "detalhe sensível"}}, request=request)

    def fail_run():
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(e2e, "run", fail_run)

    assert e2e.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "FAIL",
        "stage": "resource_http",
        "http_status": 403,
        "request_host": "api.powerplatform.com",
    }


def test_main_retorna_erro_oauth_estruturado_sem_descricao(monkeypatch, capsys):
    from app.services.microsoft_oauth import MicrosoftOAuthError

    def fail_run():
        raise MicrosoftOAuthError(
            resource="power_platform",
            status_code=401,
            error_code="invalid_client",
            aadsts_code="AADSTS7000215",
            trace_id="trace-1",
            correlation_id="corr-1",
        )

    monkeypatch.setattr(e2e, "run", fail_run)

    assert e2e.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["oauth_error"]["aadsts_code"] == "AADSTS7000215"
    assert payload["oauth_error"]["correlation_id"] == "corr-1"
    assert "client_secret" not in json.dumps(payload)
