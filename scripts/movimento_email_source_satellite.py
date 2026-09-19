#!/usr/bin/env python3
"""Descobre e valida uma origem SQL corporativa para Prospecção Movimento.

O satélite não lê linhas de negócio. Usa apenas metadados SQL, autenticação
integrada do Windows, TLS obrigatório e ApplicationIntent=ReadOnly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

EXPECTED_FUNCTION = "CNS.PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA"
PATTERNS = ("prospec", "movimento", "pendenc", "fechamento", "consign", "portab")
SAFE_SQL_NAME = re.compile(r"^[A-Za-z0-9_.\\\\-]+$")


@dataclass(frozen=True)
class Candidate:
    server: str
    database: str
    origin: str


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def validate_candidate(candidate: Candidate) -> Candidate:
    server = candidate.server.strip()
    database = candidate.database.strip()
    if not server or not database:
        raise ValueError("candidate_server_database_required")
    if not SAFE_SQL_NAME.fullmatch(server):
        raise ValueError("candidate_server_invalid")
    if not SAFE_SQL_NAME.fullmatch(database):
        raise ValueError("candidate_database_invalid")
    return Candidate(server=server, database=database, origin=candidate.origin.strip() or "unknown")


def choose_driver(installed: Iterable[str]) -> str:
    available = set(installed)
    for candidate in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if candidate in available:
            return candidate
    raise RuntimeError("no_supported_sql_server_odbc_driver")


def build_dsn(candidate: Candidate, driver: str) -> str:
    candidate = validate_candidate(candidate)
    if driver not in {"ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"}:
        raise ValueError("sql_driver_invalid")
    return (
        f"Driver={{{driver}}};"
        f"Server={candidate.server};Database={candidate.database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=no;"
        "ApplicationIntent=ReadOnly;"
        "Connection Timeout=8;"
    )


def parse_env_candidates(raw: str) -> list[Candidate]:
    if not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("source_candidates_json_invalid") from exc
    if not isinstance(payload, list):
        raise ValueError("source_candidates_must_be_list")
    result: list[Candidate] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("source_candidate_must_be_object")
        result.append(validate_candidate(Candidate(
            server=str(item.get("server") or ""),
            database=str(item.get("database") or ""),
            origin=str(item.get("origin") or "environment"),
        )))
    return result


def _registry_candidates_from_root(winreg: Any, hive: Any, root_path: str, origin: str) -> list[Candidate]:
    result: list[Candidate] = []
    try:
        with winreg.OpenKey(hive, root_path + r"\ODBC Data Sources") as names_key:
            index = 0
            names: list[str] = []
            while True:
                try:
                    name, _value, _kind = winreg.EnumValue(names_key, index)
                    names.append(str(name))
                    index += 1
                except OSError:
                    break
        for dsn_name in names:
            try:
                with winreg.OpenKey(hive, root_path + "\\" + dsn_name) as dsn_key:
                    server = str(winreg.QueryValueEx(dsn_key, "Server")[0] or "").strip()
                    try:
                        database = str(winreg.QueryValueEx(dsn_key, "Database")[0] or "").strip()
                    except OSError:
                        database = ""
                if server and database:
                    result.append(validate_candidate(Candidate(server, database, origin)))
            except (OSError, ValueError):
                continue
    except OSError:
        return []
    return result


def registry_candidates() -> list[Candidate]:
    if os.name != "nt":
        return []
    import winreg  # type: ignore

    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\ODBC\ODBC.INI", "registry_hkcu"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ODBC\ODBC.INI", "registry_hklm"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\ODBC\ODBC.INI", "registry_hklm32"),
    ]
    result: list[Candidate] = []
    for hive, root_path, origin in roots:
        result.extend(_registry_candidates_from_root(winreg, hive, root_path, origin))
    return result


def dedupe_candidates(items: Iterable[Candidate]) -> list[Candidate]:
    result: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for raw in items:
        candidate = validate_candidate(raw)
        key = (candidate.server.casefold(), candidate.database.casefold())
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def probe_network(server: str, *, port: int = 1433, timeout: float = 3.0) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "dns_resolved": False,
        "tcp_reachable": False,
        "resolved_address_hashes": [],
    }
    try:
        addresses = socket.getaddrinfo(server, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        evidence.update({"dns_error_type": type(exc).__name__, "dns_error_code": getattr(exc, "errno", None)})
        return evidence
    unique = sorted({str(item[4][0]) for item in addresses})
    evidence["dns_resolved"] = bool(unique)
    evidence["resolved_address_hashes"] = [short_hash(value) for value in unique]
    for address in unique:
        try:
            with socket.create_connection((address, port), timeout=timeout):
                evidence["tcp_reachable"] = True
                break
        except OSError:
            continue
    return evidence


def inspect_sql_metadata(conn: Any) -> dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME(), "
        "IS_SRVROLEMEMBER('sysadmin'), IS_MEMBER('db_owner'), IS_MEMBER('db_datawriter')"
    )
    server_name, database_name, sysadmin, db_owner, db_datawriter = cur.fetchone()
    broad_write_role = any(int(value or 0) == 1 for value in (sysadmin, db_owner, db_datawriter))

    cur.execute(
        "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
        "FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"
    )
    objects: list[str] = []
    for schema, name, kind in cur.fetchall():
        name_text = str(name or "")
        if any(pattern in name_text.casefold() for pattern in PATTERNS):
            objects.append(f"{schema}.{name_text}:{kind}")

    cur.execute(
        "SELECT CASE WHEN OBJECT_ID(N'CNS.PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA') "
        "IS NULL THEN 0 ELSE 1 END"
    )
    expected_function_present = bool(cur.fetchone()[0])
    function_columns: list[str] = []
    function_metadata_status = "not_present"
    if expected_function_present:
        try:
            cur.execute(
                "SELECT name FROM sys.dm_exec_describe_first_result_set("
                "N'SELECT * FROM CNS.PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA()', NULL, 0) "
                "WHERE is_hidden=0 AND error_number IS NULL ORDER BY column_ordinal"
            )
            function_columns = [str(row[0]) for row in cur.fetchall() if row[0]]
            function_metadata_status = "described"
        except Exception:
            function_metadata_status = "unavailable"

    return {
        "resolved_server_hash": short_hash(str(server_name or "")),
        "resolved_database_hash": short_hash(str(database_name or "")),
        "broad_write_role_detected": broad_write_role,
        "candidate_objects": objects[:100],
        "expected_function_present": expected_function_present,
        "expected_function_columns": function_columns,
        "expected_function_metadata_status": function_metadata_status,
    }


def probe_candidate(
    candidate: Candidate,
    *,
    network_fn: Callable[[str], dict[str, Any]] = probe_network,
    connect_fn: Callable[[str], Any] | None = None,
    installed_drivers: Iterable[str] | None = None,
) -> dict[str, Any]:
    candidate = validate_candidate(candidate)
    evidence: dict[str, Any] = {
        "source_server_hash": short_hash(candidate.server),
        "source_database_hash": short_hash(candidate.database),
        "origin": candidate.origin,
        "auth": "windows_integrated",
        "encrypt": True,
        "trust_server_certificate": False,
        "application_intent": "ReadOnly",
        "secret_used": False,
        "business_rows_read": False,
        "write_attempted": False,
        "connected": False,
        "passed": False,
    }
    network = network_fn(candidate.server)
    evidence["network"] = network
    if not network.get("dns_resolved") or not network.get("tcp_reachable"):
        evidence["status"] = "blocked_network"
        return evidence

    if connect_fn is None:
        import pyodbc
        driver = choose_driver(installed_drivers if installed_drivers is not None else pyodbc.drivers())
        dsn = build_dsn(candidate, driver)
        connect_fn = lambda value: pyodbc.connect(value, timeout=8, autocommit=True)
    else:
        driver = choose_driver(installed_drivers or ("ODBC Driver 18 for SQL Server",))
        dsn = build_dsn(candidate, driver)

    try:
        conn = connect_fn(dsn)
        try:
            metadata = inspect_sql_metadata(conn)
        finally:
            conn.close()
    except Exception as exc:
        evidence.update({
            "status": "blocked_sql",
            "error_type": type(exc).__name__,
            "error": str(exc).splitlines()[0][:240],
        })
        return evidence

    evidence.update(metadata)
    evidence["connected"] = True
    if metadata["broad_write_role_detected"]:
        evidence["status"] = "blocked_write_privilege"
        return evidence
    evidence["passed"] = bool(metadata["expected_function_present"] or metadata["candidate_objects"])
    evidence["status"] = "validated" if evidence["passed"] else "connected_no_candidate"
    return evidence


def parse_cli_candidate(value: str) -> Candidate:
    if "|" not in value:
        raise argparse.ArgumentTypeError("candidate deve usar SERVER|DATABASE")
    server, database = value.split("|", 1)
    try:
        return validate_candidate(Candidate(server, database, "cli"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def run(candidates: Iterable[Candidate]) -> dict[str, Any]:
    unique = dedupe_candidates(candidates)
    attempts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for candidate in unique:
        result = probe_candidate(candidate)
        attempts.append(result)
        if result.get("passed"):
            selected = result
            break
    return {
        "schema_version": "1.0.0",
        "feature": "movimento_email_source_satellite",
        "candidate_count": len(unique),
        "attempts": attempts,
        "selected": selected,
        "source_validated": selected is not None,
        "secret_exposed": False,
        "business_rows_read": False,
        "write_attempted": False,
        "production_touched": False,
        "status": "validated" if selected else ("blocked" if unique else "no_candidates"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", action="append", type=parse_cli_candidate, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    env_items = parse_env_candidates(os.getenv("MOVIMENTO_EMAIL_SOURCE_CANDIDATES", ""))
    payload = run([*args.candidate, *env_items, *registry_candidates()])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["source_validated"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
