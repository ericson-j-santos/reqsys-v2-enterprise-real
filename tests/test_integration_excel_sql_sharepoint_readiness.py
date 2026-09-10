from __future__ import annotations

import json

import httpx
import pytest

from scripts.integration_excel_sql_sharepoint_readiness import (
    ReadinessConfig,
    ReadinessError,
    run_readiness,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("GET", "https://example.invalid")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "erro",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )


class FakeClient:
    def __init__(self, *, graph_status: int = 200):
        self.graph_status = graph_status
        self.closed = False

    def post(self, url, **kwargs):
        return FakeResponse({"access_token": "token-de-teste"})

    def get(self, url, **kwargs):
        if self.graph_status >= 400:
            return FakeResponse({}, self.graph_status)
        if "/drives/" in url:
            return FakeResponse({"id": "file-1", "name": "entrada.xlsx", "eTag": "etag"})
        if "/sites/" in url and "/lists/" in url:
            return FakeResponse({"id": "list-1", "displayName": "ResultadoConsulta"})
        return FakeResponse({})

    def close(self):
        self.closed = True


def valid_config(**overrides) -> ReadinessConfig:
    values = {
        "environment": "dev",
        "tenant_id": "tenant",
        "client_id": "client",
        "client_secret": "segredo-que-nao-pode-vazar",
        "drive_id": "drive",
        "file_id": "file",
        "site_id": "site",
        "list_id": "list",
        "sql_dsn": "dsn-secreto",
        "sql_procedure": "integration.usp_ConsultarPorIdentificadores",
        "power_platform_environment_id": "Default-env",
        "excel_connection_id": "excel-connection",
        "sql_connection_id": "sql-connection",
        "sharepoint_connection_id": "sharepoint-connection",
    }
    values.update(overrides)
    return ReadinessConfig(**values)


def test_readiness_passes_only_when_all_dependencies_are_realistically_ready():
    result = run_readiness(
        valid_config(),
        client=FakeClient(),
        sql_checker=lambda _: {"status": "passed", "procedure_exists": True},
    )

    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["checks"]["excel_source"]["resource_name"] == "entrada.xlsx"
    assert result["checks"]["sharepoint_destination"]["resource_name"] == "ResultadoConsulta"


def test_missing_configuration_fails_closed_without_exposing_secret_material():
    result = run_readiness(
        valid_config(sql_dsn="", sharepoint_connection_id=""),
        client=FakeClient(),
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["ready"] is False
    assert "configuration" in result["blockers"]
    assert "sql_server" in result["blockers"]
    assert "power_automate_connections" in result["blockers"]
    assert "segredo-que-nao-pode-vazar" not in serialized
    assert "dsn-secreto" not in serialized


def test_graph_failure_is_reported_as_sanitized_blocker():
    result = run_readiness(
        valid_config(),
        client=FakeClient(graph_status=403),
        sql_checker=lambda _: {"status": "passed", "procedure_exists": True},
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["ready"] is False
    assert "excel_source" in result["blockers"]
    assert "sharepoint_destination" in result["blockers"]
    assert "http_status_403" in serialized
    assert "segredo-que-nao-pode-vazar" not in serialized


def test_non_dev_environment_is_rejected():
    with pytest.raises(ReadinessError, match="restrito_a_dev"):
        run_readiness(valid_config(environment="prod"), client=FakeClient())
