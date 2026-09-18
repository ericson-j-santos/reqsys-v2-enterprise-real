#!/usr/bin/env python3
"""Probe somente leitura para confirmar metadados da origem SQL da Prospecção Movimento.

Não recebe usuário/senha. Usa autenticação integrada do Windows, TLS com
validação de certificado e ApplicationIntent=ReadOnly. A saída nunca imprime
connection string nem nomes de host/banco em texto puro; apenas hashes e
objetos SQL candidatos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\\-]+$")
_PATTERNS = ("prospec", "movimento", "pendenc", "fechamento", "consign", "portab")
_EXPECTED_FUNCTION = "PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def build_dsn(server: str, database: str) -> str:
    if not _SAFE_NAME.fullmatch(server):
        raise ValueError("invalid_server")
    if not _SAFE_NAME.fullmatch(database):
        raise ValueError("invalid_database")
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=no;"
        "ApplicationIntent=ReadOnly;"
        "Connection Timeout=8;"
    )


def probe(server: str, database: str) -> dict[str, Any]:
    import pyodbc

    dsn = build_dsn(server, database)
    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "movimento_email_source_readonly_probe",
        "source_server_hash": _hash(server),
        "source_database_hash": _hash(database),
        "auth": "windows_integrated",
        "encrypt": True,
        "trust_server_certificate": False,
        "application_intent": "ReadOnly",
        "secret_used": False,
        "write_attempted": False,
        "connected": False,
        "candidate_objects": [],
        "expected_function_present": False,
    }

    conn = pyodbc.connect(dsn, timeout=8, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME(), "
            "CAST(DATABASEPROPERTYEX(DB_NAME(),'Updateability') AS nvarchar(60))"
        )
        server_name, database_name, updateability = cur.fetchone()
        evidence["connected"] = True
        evidence["resolved_server_hash"] = _hash(str(server_name or ""))
        evidence["resolved_database_hash"] = _hash(str(database_name or ""))
        evidence["database_updateability"] = str(updateability or "")

        cur.execute(
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
            "FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"
        )
        candidates: list[str] = []
        for schema, name, kind in cur.fetchall():
            name_text = str(name or "")
            if any(p in name_text.casefold() for p in _PATTERNS):
                candidates.append(f"{schema}.{name_text}:{kind}")
        evidence["candidate_objects"] = candidates[:100]

        cur.execute(
            "SELECT CASE WHEN OBJECT_ID(N'CNS.PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA') "
            "IS NULL THEN 0 ELSE 1 END"
        )
        evidence["expected_function_present"] = bool(cur.fetchone()[0])
        evidence["passed"] = bool(
            evidence["connected"]
            and (
                evidence["expected_function_present"]
                or len(evidence["candidate_objects"]) > 0
            )
        )
        return evidence
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    try:
        result = probe(args.server, args.database)
    except Exception as exc:
        result = {
            "schema_version": "1.0.0",
            "feature": "movimento_email_source_readonly_probe",
            "source_server_hash": _hash(args.server),
            "source_database_hash": _hash(args.database),
            "auth": "windows_integrated",
            "encrypt": True,
            "trust_server_certificate": False,
            "application_intent": "ReadOnly",
            "secret_used": False,
            "write_attempted": False,
            "connected": False,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc).splitlines()[0][:240],
        }
        print(json.dumps(result, ensure_ascii=False))
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
