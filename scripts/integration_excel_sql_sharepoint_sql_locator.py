#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_PROCEDURE = "integration.usp_ConsultarPorIdentificadores"


class SqlLocatorError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def parameter_contract_ok(parameters: list[tuple[str, str, int, bool]]) -> bool:
    normalized = {
        text(name).casefold(): (text(type_name).casefold(), int(max_length), bool(is_output))
        for name, type_name, max_length, is_output in parameters
    }
    ids = normalized.get("@idsjson")
    correlation = normalized.get("@correlationid")
    return bool(
        ids == ("nvarchar", -1, False)
        and correlation == ("uniqueidentifier", 16, False)
    )


def safe_error(exc: Exception) -> str:
    if isinstance(exc, SqlLocatorError):
        code = text(exc)
        if code in {
            "ambiente_nao_dev",
            "sql_dsn_ausente",
            "pyodbc_ausente",
            "stored_procedure_ausente",
            "contrato_parametros_invalido",
        }:
            return code
    return exc.__class__.__name__


def probe_sql(
    dsn: str,
    procedure: str,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not dsn:
        raise SqlLocatorError("sql_dsn_ausente")

    if connect is None:
        try:
            import pyodbc
        except ImportError as exc:  # pragma: no cover - depende do runner real
            raise SqlLocatorError("pyodbc_ausente") from exc
        connect = pyodbc.connect

    connection = None
    try:
        connection = connect(dsn, timeout=10)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME(), "
            "CASE WHEN OBJECT_ID(?, 'P') IS NULL THEN 0 ELSE 1 END",
            procedure,
        )
        context = cursor.fetchone()
        if not context:
            raise SqlLocatorError("stored_procedure_ausente")

        server_name = text(context[0])
        database_name = text(context[1])
        procedure_exists = bool(int(context[2]))
        if not procedure_exists:
            raise SqlLocatorError("stored_procedure_ausente")

        cursor.execute(
            "SELECT p.name, TYPE_NAME(p.user_type_id), p.max_length, p.is_output "
            "FROM sys.parameters AS p "
            "WHERE p.object_id = OBJECT_ID(?, 'P') "
            "ORDER BY p.parameter_id",
            procedure,
        )
        parameters = [
            (text(row[0]), text(row[1]), int(row[2]), bool(row[3]))
            for row in cursor.fetchall()
        ]
        contract_ok = parameter_contract_ok(parameters)
        if not contract_ok:
            raise SqlLocatorError("contrato_parametros_invalido")

        return {
            "procedure": procedure,
            "procedure_exists": True,
            "parameter_contract_ok": True,
            "server_hash": digest(server_name),
            "database_hash": digest(database_name),
            "locator_hash": digest(f"{server_name}/{database_name}/{procedure}"),
        }
    finally:
        if connection is not None:
            connection.close()


def run_probe() -> dict[str, Any]:
    environment = text(os.getenv("INTEGRATION_E2E_ENVIRONMENT", "dev")).casefold()
    if environment not in {"dev", "development"}:
        raise SqlLocatorError("ambiente_nao_dev")
    procedure = text(os.getenv("INTEGRATION_E2E_SQL_PROCEDURE")) or DEFAULT_PROCEDURE
    dsn = text(os.getenv("INTEGRATION_E2E_SQL_DSN"))
    result = probe_sql(dsn, procedure)
    return {
        "status": "resolved",
        "environment": "dev",
        "dsn_present": True,
        **result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Descoberta segura do locator SQL do E2E DEV")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--source-sha", default=text(os.getenv("GITHUB_SHA")))
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args()

    correlation_id = text(args.correlation_id) or str(uuid.uuid4())
    base = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_sql_locator",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_sha": text(args.source_sha),
        "correlation_id": correlation_id,
        "mocked": False,
        "simulated": False,
    }

    try:
        payload = {**base, **run_probe(), "error": None}
    except Exception as exc:
        payload = {
            **base,
            "status": "blocked",
            "environment": text(os.getenv("INTEGRATION_E2E_ENVIRONMENT", "dev")),
            "dsn_present": bool(text(os.getenv("INTEGRATION_E2E_SQL_DSN"))),
            "procedure": text(os.getenv("INTEGRATION_E2E_SQL_PROCEDURE")) or DEFAULT_PROCEDURE,
            "procedure_exists": False,
            "parameter_contract_ok": False,
            "error": safe_error(exc),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "environment": payload["environment"],
        "procedure": payload["procedure"],
        "procedure_exists": payload["procedure_exists"],
        "parameter_contract_ok": payload["parameter_contract_ok"],
        "error": payload["error"],
    }, ensure_ascii=False))
    return 1 if args.strict and payload["status"] != "resolved" else 0


if __name__ == "__main__":
    raise SystemExit(main())
