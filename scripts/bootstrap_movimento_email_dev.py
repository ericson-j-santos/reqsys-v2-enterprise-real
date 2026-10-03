#!/usr/bin/env python3
"""Cria a infraestrutura SQL DEV da Prospecção Movimento sem segredos.

Uso:
  python scripts/bootstrap_movimento_email_dev.py --seed-e2e

O script usa autenticação integrada do Windows por padrão e é destinado
somente a DEV/local. Ele não cria login, usuário, segredo ou permissão.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "dev"
VIEWS_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "views"

VIEWS = {
    "vw_prospeccao_movimento_fechamento_diario": 4,
    "vw_prospeccao_movimento_pendencias_cadastro": 7,
    "vw_prospeccao_movimento_pendencias_historicas": 5,
    "vw_prospeccao_movimento_pendencias_observacao": 5,
}


def _safe_database_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise SystemExit("Nome de banco inválido; use apenas letras, números e _.")
    return value


def _connect(server: str, database: str, *, autocommit: bool = False):
    import pyodbc

    return pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
        timeout=10,
        autocommit=autocommit,
    )


def _execute_file(cursor, path: Path) -> None:
    cursor.execute(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--database", default="ReqSysMovimentoDev")
    parser.add_argument("--seed-e2e", action="store_true")
    args = parser.parse_args()

    database = _safe_database_name(args.database)

    master = _connect(args.server, "master", autocommit=True)
    try:
        master.cursor().execute(
            f"IF DB_ID('{database}') IS NULL CREATE DATABASE [{database}]"
        )
    finally:
        master.close()

    conn = _connect(args.server, database, autocommit=False)
    try:
        cur = conn.cursor()
        _execute_file(cur, DEV_SQL / "V1__source_schema.sql")
        for filename in (
            "V2__vw_prospeccao_movimento_fechamento_diario.sql",
            "V2__vw_prospeccao_movimento_pendencias_cadastro.sql",
            "V2__vw_prospeccao_movimento_pendencias_historicas.sql",
            "V2__vw_prospeccao_movimento_pendencias_observacao.sql",
        ):
            _execute_file(cur, VIEWS_SQL / filename)
        if args.seed_e2e:
            _execute_file(cur, DEV_SQL / "V1__seed_e2e.sql")
        conn.commit()

        evidence = {}
        for view, expected_columns in VIEWS.items():
            cur.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?",
                view,
            )
            evidence[view] = {
                "columns": int(cur.fetchone()[0]),
                "expected_columns": expected_columns,
            }

        result = {
            "status": "validated"
            if all(v["columns"] == v["expected_columns"] for v in evidence.values())
            else "failed",
            "server": args.server,
            "database": database,
            "schema": "movimento_src",
            "views": evidence,
            "seed_e2e": args.seed_e2e,
            "corporate_source_validated": False,
            "secrets_used": False,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "validated" else 3
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
