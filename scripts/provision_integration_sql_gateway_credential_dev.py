#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import json
import os
import secrets
import string
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE = "ReqSysIntegrationDev"
LOGIN = "reqsys_e2e_gateway_dev"
PROCEDURE = "integration.usp_ConsultarPorIdentificadores"
CREDENTIAL_TARGET = "ReqSys/PowerPlatform/SQL-DEV"
FIXTURE_ID = "990000000000001"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_password(length: int = 48) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+="
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(ch in group for ch in value) for group in (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*_-+=")):
            return value


def sql_quote(value: str) -> str:
    return value.replace("'", "''")


def login_ddl(password: str) -> str:
    escaped = sql_quote(password)
    return f"""
IF EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = N'{LOGIN}')
    ALTER LOGIN [{LOGIN}] WITH PASSWORD = N'{escaped}', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
ELSE
    CREATE LOGIN [{LOGIN}] WITH PASSWORD = N'{escaped}', CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
""".strip()


def user_ddl() -> str:
    return f"""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{LOGIN}')
    CREATE USER [{LOGIN}] FOR LOGIN [{LOGIN}];
GRANT CONNECT TO [{LOGIN}];
GRANT EXECUTE ON OBJECT::{PROCEDURE} TO [{LOGIN}];
""".strip()


def sql_connection_string(driver: str, server: str, database: str, password: str) -> str:
    return (
        f"Driver={{{driver}}};Server={server};Database={database};Uid={LOGIN};Pwd={password};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )


def driver_candidates() -> list[str]:
    import pyodbc

    installed = set(pyodbc.drivers())
    return [x for x in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server") if x in installed]


def connect_integrated(server: str, database: str, *, autocommit: bool = False):
    import pyodbc

    last_error: Exception | None = None
    for driver in driver_candidates():
        try:
            cs = (
                f"Driver={{{driver}}};Server={server};Database={database};"
                "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
            )
            return pyodbc.connect(cs, timeout=15, autocommit=autocommit), driver
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError("integrated_sql_connection_failed") from last_error


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def credential_write(password: str) -> None:
    if os.name != "nt":
        raise RuntimeError("windows_required")
    blob = password.encode("utf-16-le")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    credential = CREDENTIALW()
    credential.Flags = 0
    credential.Type = 1
    credential.TargetName = CREDENTIAL_TARGET
    credential.Comment = "ReqSys Excel-SQL-SharePoint DEV gateway credential"
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = 2
    credential.AttributeCount = 0
    credential.Attributes = None
    credential.TargetAlias = None
    credential.UserName = LOGIN
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError()


def execute_probe(cursor, fixture_id: str = FIXTURE_ID) -> None:
    correlation_id = str(uuid.uuid4())
    cursor.execute(
        f"EXEC {PROCEDURE} @IdsJson=?, @CorrelationId=?",
        json.dumps([fixture_id]),
        correlation_id,
    )
    row = cursor.fetchone()
    if row is None or str(row[0]) != fixture_id:
        raise RuntimeError("sql_login_execute_probe_failed")


def verify_login(server: str, driver: str, password: str) -> None:
    import pyodbc

    connection = pyodbc.connect(sql_connection_string(driver, server, DATABASE, password), timeout=15)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME(), ORIGINAL_LOGIN()")
        database, login = cursor.fetchone()
        if str(database) != DATABASE or str(login).casefold() != LOGIN.casefold():
            raise RuntimeError("sql_login_context_invalid")
        execute_probe(cursor)
    finally:
        connection.close()


def provision(server: str) -> dict[str, Any]:
    password = generate_password()
    master, driver = connect_integrated(server, "master", autocommit=True)
    try:
        master.cursor().execute(login_ddl(password))
    finally:
        master.close()

    database, _ = connect_integrated(server, DATABASE, autocommit=False)
    try:
        cursor = database.cursor()
        cursor.execute(user_ddl())
        database.commit()
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()

    verify_login(server, driver, password)
    credential_write(password)
    return {
        "status": "passed",
        "environment": "dev",
        "database": DATABASE,
        "login": LOGIN,
        "procedure": PROCEDURE,
        "authentication": "sql_password",
        "credential_store": "windows_credential_manager",
        "credential_target": CREDENTIAL_TARGET,
        "least_privilege": True,
        "grants": ["CONNECT", f"EXECUTE:{PROCEDURE}"],
        "positive_execute_probe": "passed",
        "password_exposed": False,
        "production_touched": False,
        "test_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Provisiona credencial SQL DEV dedicada ao Gateway do ReqSys")
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    base = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_gateway_sql_credential",
        "captured_at": utcnow(),
        "mocked": False,
        "simulated": False,
    }
    try:
        payload = {**base, **provision(args.server), "error": None}
        exit_code = 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            **base,
            "status": "blocked",
            "environment": "dev",
            "database": DATABASE,
            "login": LOGIN,
            "procedure": PROCEDURE,
            "password_exposed": False,
            "production_touched": False,
            "test_touched": False,
            "error": exc.__class__.__name__,
        }
        exit_code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload.get(k) for k in ("status", "environment", "database", "login", "least_privilege", "positive_execute_probe", "password_exposed", "error")}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
