#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DATABASE = "ReqSysIntegrationDev"
DEFAULT_PROCEDURE = "integration.usp_ConsultarPorIdentificadores"
DEFAULT_FIXTURE_ID = "990000000000001"
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_database_name(value: str) -> str:
    name = str(value or "").strip()
    if not _NAME_RE.fullmatch(name) or not name.casefold().endswith("dev"):
        raise ValueError("database_name_must_be_safe_and_end_with_dev")
    return name


def driver_candidates() -> list[str]:
    try:
        import pyodbc
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("pyodbc_ausente") from exc
    installed = set(pyodbc.drivers())
    preferred = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]
    return [driver for driver in preferred if driver in installed]


def connection_string(driver: str, server: str, database: str) -> str:
    return (
        f"Driver={{{driver}}};Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )


def procedure_sql() -> str:
    return r"""
CREATE OR ALTER PROCEDURE integration.usp_ConsultarPorIdentificadores
    @IdsJson nvarchar(max),
    @CorrelationId uniqueidentifier
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH ids AS (
        SELECT CONVERT(nvarchar(64), [value]) AS Identificador
        FROM OPENJSON(@IdsJson)
        WHERE [type] IN (1, 2)
    )
    SELECT
        d.Identificador,
        d.Descricao,
        @CorrelationId AS CorrelationId
    FROM ids
    INNER JOIN integration.E2EIdentificadores AS d
        ON d.Identificador = ids.Identificador;
END
""".strip()


def connect_first(server: str, database: str, *, autocommit: bool = False):
    import pyodbc

    last_error: Exception | None = None
    for driver in driver_candidates():
        try:
            return pyodbc.connect(
                connection_string(driver, server, database),
                timeout=15,
                autocommit=autocommit,
            ), driver
        except Exception as exc:  # noqa: BLE001 - sanitizado no chamador
            last_error = exc
    raise RuntimeError("sql_local_connection_failed") from last_error


def ensure_database(server: str, database: str) -> tuple[bool, str]:
    connection, driver = connect_first(server, "master", autocommit=True)
    created = False
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_ID(?)", database)
        exists = cursor.fetchone()[0] is not None
        if not exists:
            cursor.execute(f"CREATE DATABASE [{database}]")
            created = True
    finally:
        connection.close()
    return created, driver


def provision(server: str, database: str, fixture_id: str) -> dict[str, Any]:
    database = validate_database_name(database)
    if not fixture_id.isdigit():
        raise ValueError("fixture_id_must_be_numeric")

    database_created, driver = ensure_database(server, database)
    connection, _ = connect_first(server, database, autocommit=False)
    try:
        cursor = connection.cursor()
        cursor.execute("IF SCHEMA_ID('integration') IS NULL EXEC('CREATE SCHEMA integration')")
        cursor.execute(
            """
IF OBJECT_ID('integration.E2EIdentificadores', 'U') IS NULL
BEGIN
    CREATE TABLE integration.E2EIdentificadores (
        Identificador nvarchar(64) NOT NULL PRIMARY KEY,
        Descricao nvarchar(200) NOT NULL,
        Synthetic bit NOT NULL CONSTRAINT DF_E2EIdentificadores_Synthetic DEFAULT (1),
        CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_E2EIdentificadores_CreatedAt DEFAULT (sysutcdatetime())
    )
END
"""
        )
        cursor.execute(
            """
IF NOT EXISTS (SELECT 1 FROM integration.E2EIdentificadores WHERE Identificador = ?)
    INSERT INTO integration.E2EIdentificadores (Identificador, Descricao, Synthetic)
    VALUES (?, N'ReqSys E2E DEV fixture', 1)
""",
            fixture_id,
            fixture_id,
        )
        cursor.execute(procedure_sql())
        connection.commit()

        cursor.execute(
            "SELECT p.name, TYPE_NAME(p.user_type_id), p.max_length, p.is_output "
            "FROM sys.parameters AS p WHERE p.object_id = OBJECT_ID(?, 'P') ORDER BY p.parameter_id",
            DEFAULT_PROCEDURE,
        )
        parameters = [tuple(row) for row in cursor.fetchall()]
        normalized = {
            str(name).casefold(): (str(type_name).casefold(), int(max_length), bool(is_output))
            for name, type_name, max_length, is_output in parameters
        }
        contract_ok = (
            normalized.get("@idsjson") == ("nvarchar", -1, False)
            and normalized.get("@correlationid") == ("uniqueidentifier", 16, False)
        )
        if not contract_ok:
            raise RuntimeError("contrato_parametros_invalido")

        correlation = str(uuid.uuid4())
        cursor.execute(
            f"EXEC {DEFAULT_PROCEDURE} @IdsJson=?, @CorrelationId=?",
            json.dumps([fixture_id]),
            correlation,
        )
        positive = cursor.fetchone()
        if positive is None or str(positive[0]) != fixture_id:
            raise RuntimeError("positive_probe_failed")

        cursor.execute(
            f"EXEC {DEFAULT_PROCEDURE} @IdsJson=?, @CorrelationId=?",
            json.dumps(["999999999999999"]),
            correlation,
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("negative_probe_failed")

        cursor.execute("SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME()")
        server_name, database_name = cursor.fetchone()
        return {
            "status": "passed",
            "environment": "dev",
            "database_created": database_created,
            "schema_ready": True,
            "fixture_ready": True,
            "procedure": DEFAULT_PROCEDURE,
            "procedure_exists": True,
            "parameter_contract_ok": True,
            "positive_probe": "passed",
            "negative_probe": "passed",
            "server_hash": digest(str(server_name or "")),
            "database_hash": digest(str(database_name or "")),
            "fixture_hash": digest(fixture_id),
            "driver": driver,
            "secret_exposed": False,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Provisiona SQL DEV isolado para o E2E Excel -> SQL -> SharePoint")
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--fixture-id", default=DEFAULT_FIXTURE_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_dev_sql_provisioning",
        "captured_at": utcnow(),
        "mocked": False,
        "simulated": False,
    }
    try:
        payload = {**base, **provision(args.server, args.database, args.fixture_id), "error": None}
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - resposta sanitizada
        payload = {
            **base,
            "status": "blocked",
            "environment": "dev",
            "procedure": DEFAULT_PROCEDURE,
            "secret_exposed": False,
            "error": exc.__class__.__name__,
        }
        exit_code = 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload.get(key) for key in ("status", "environment", "procedure", "parameter_contract_ok", "positive_probe", "negative_probe", "error")}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
