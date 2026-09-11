from __future__ import annotations

import json
from io import BytesIO

import pytest
from openpyxl import Workbook
from openpyxl.worksheet.table import Table

from scripts.integration_excel_sql_sharepoint_discovery import (
    DiscoveryError,
    choose_connection,
    choose_environment,
    evidence,
    has_table,
    runtime_values,
    safe_error,
    write_github_env,
)


def env(environment_id: str, name: str, sku: str = "Sandbox") -> dict:
    return {
        "name": environment_id,
        "displayName": name,
        "properties": {
            "environmentId": environment_id,
            "environmentSku": sku,
            "environmentUrl": f"https://{environment_id}.example.invalid",
        },
    }


def conn(connection_id: str, marker: str, name: str, status: str = "Connected") -> dict:
    return {
        "name": connection_id,
        "properties": {
            "apiId": f"/providers/Microsoft.PowerApps/apis/{marker}",
            "displayName": name,
            "status": status,
        },
    }


def fixtures():
    contract = {
        "table": "tbEntrada",
        "list": "ResultadoConsulta",
        "procedure": "integration.usp_ConsultarPorIdentificadores",
    }
    sp = {
        "site_id": "site-id-privado",
        "site_name": "ReqSys DEV",
        "site_url": "https://tenant.sharepoint.com/sites/reqsys-dev",
        "list_id": "list-id-privado",
        "list_name": "ResultadoConsulta",
        "drive_id": "drive-id-privado",
        "drive_name": "Documentos",
        "file_id": "file-id-privado",
        "file_name": "entrada.xlsx",
    }
    pp = {
        "environment_id": "environment-id-privado",
        "environment_name": "ReqSys DEV",
        "excel_connection_id": "excel-connection-privada",
        "sql_connection_id": "sql-connection-privada",
        "sharepoint_connection_id": "sp-connection-privada",
    }
    return contract, sp, pp


def test_environment_selection_is_fail_closed():
    selected = choose_environment([env("env-prod", "ReqSys PROD", "Production"), env("env-dev", "ReqSys DEV")])
    assert selected["name"] == "env-dev"

    with pytest.raises(DiscoveryError, match="ambiente_ambiguo"):
        choose_environment([env("env-dev-a", "ReqSys DEV A"), env("env-dev-b", "ReqSys DEV B")])


def test_connection_selection_ignores_broken_and_rejects_ambiguity():
    selected = choose_connection(
        [
            conn("excel-ok", "shared_excelonlinebusiness", "Excel DEV"),
            conn("excel-broken", "shared_excelonlinebusiness", "Excel antigo", "Error"),
        ],
        "shared_excelonlinebusiness",
    )
    assert selected["name"] == "excel-ok"

    with pytest.raises(DiscoveryError, match="conexao_shared_sql_ambigua"):
        choose_connection(
            [conn("sql-a", "shared_sql", "SQL A"), conn("sql-b", "shared_sql", "SQL B")],
            "shared_sql",
        )


def test_real_workbook_table_contract_is_detected():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Identificador"])
    sheet.append(["123"])
    sheet.add_table(Table(displayName="tbEntrada", ref="A1:A2"))
    stream = BytesIO()
    workbook.save(stream)

    assert has_table(stream.getvalue(), "tbEntrada") is True
    assert has_table(stream.getvalue(), "OutraTabela") is False


def test_evidence_hashes_private_ids_and_never_serializes_dsn(monkeypatch):
    contract, sp, pp = fixtures()
    resolved = runtime_values(contract, sp, pp)
    monkeypatch.setenv("INTEGRATION_E2E_SQL_DSN", "Driver=segredo;Pwd=nao-vazar")
    payload = evidence(contract, sp, pp, resolved, "sha-1", "corr-1", "resolved_non_secret", None)
    raw = json.dumps(payload, ensure_ascii=False)

    assert payload["secret_presence"]["INTEGRATION_E2E_SQL_DSN"] is True
    assert payload["unresolved_secrets"] == []
    assert "site-id-privado" not in raw
    assert "file-id-privado" not in raw
    assert "environment-id-privado" not in raw
    assert "nao-vazar" not in raw
    assert set(payload["resolved"]["variable_names"]) == set(resolved)


def test_safe_error_does_not_serialize_exception_text():
    secret_marker = "Pwd=nao-vazar"
    rendered = safe_error(DiscoveryError(secret_marker))

    assert rendered == "DiscoveryError"
    assert secret_marker not in rendered


def test_runtime_values_are_written_only_to_ephemeral_github_env(tmp_path):
    contract, sp, pp = fixtures()
    resolved = runtime_values(contract, sp, pp)
    target = tmp_path / "github_env"
    write_github_env(target, resolved)
    content = target.read_text(encoding="utf-8")

    for name, value in resolved.items():
        assert f"{name}={value}" in content
