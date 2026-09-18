#!/usr/bin/env python3
"""Equivalência DEV persistente para Prospecção Movimento.

Cria uma fonte local contratualmente equivalente ao SSRS/SQL legado,
sincroniza para a camada canônica movimento_src e comprova idempotência.
Nunca representa a fonte como corporativa.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEV_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "dev"
VIEWS_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "views"

SOURCE_DB_DEFAULT = "ReqSysMovimentoSourceDev"
TARGET_DB_DEFAULT = "ReqSysMovimentoDev"
DATA_REFERENCIA = dt.date(2099, 12, 30)
SOURCE_TAG = "EQUIVALENT_DEV"

DATASETS = {
    "fechamento_diario": {
        "columns": ["indicador", "valor", "observacao", "data_referencia"],
        "rows": [
            ("EQUIV_QTD", "12", "fonte equivalente DEV", DATA_REFERENCIA),
            ("EQUIV_VALOR", "345.67", "segunda linha equivalente", DATA_REFERENCIA),
        ],
    },
    "pendencias_cadastro": {
        "columns": ["protocolo", "cliente", "cpf", "pendencia", "dias_em_aberto", "responsavel", "data_referencia"],
        "rows": [
            ("EQUIV-001", "CLIENTE DEMO", "00000000000", "DOCUMENTO", 3, "REQSYS-EQUIV", DATA_REFERENCIA),
        ],
    },
    "pendencias_historicas": {
        "columns": ["periodo_referencia", "pendencia", "quantidade", "percentual", "data_referencia"],
        "rows": [
            ("2099-12", "DOCUMENTO", 1, decimal.Decimal("100.00"), DATA_REFERENCIA),
        ],
    },
    "pendencias_observacao": {
        "columns": ["protocolo", "tipo_inconsistencia", "descricao", "etapa", "data_referencia"],
        "rows": [
            ("EQUIV-001", "VALIDACAO", "registro equivalente controlado", "EQUIVALENT_DEV", DATA_REFERENCIA),
        ],
    },
}

SOURCE_SCHEMA_SQL = """
IF SCHEMA_ID('legacy_ssrs') IS NULL EXEC('CREATE SCHEMA legacy_ssrs');

IF OBJECT_ID('legacy_ssrs.fechamento_diario','U') IS NULL
CREATE TABLE legacy_ssrs.fechamento_diario (
    indicador VARCHAR(200) NOT NULL,
    valor VARCHAR(100) NOT NULL,
    observacao VARCHAR(500) NULL,
    data_referencia DATE NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_cadastro','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_cadastro (
    protocolo VARCHAR(50) NOT NULL,
    cliente VARCHAR(200) NOT NULL,
    cpf VARCHAR(11) NOT NULL,
    pendencia VARCHAR(200) NOT NULL,
    dias_em_aberto INT NOT NULL,
    responsavel VARCHAR(120) NULL,
    data_referencia DATE NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_historicas','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_historicas (
    periodo_referencia VARCHAR(20) NOT NULL,
    pendencia VARCHAR(200) NOT NULL,
    quantidade INT NOT NULL,
    percentual DECIMAL(5,2) NOT NULL,
    data_referencia DATE NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_observacao','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_observacao (
    protocolo VARCHAR(50) NOT NULL,
    tipo_inconsistencia VARCHAR(120) NOT NULL,
    descricao VARCHAR(500) NOT NULL,
    etapa VARCHAR(120) NULL,
    data_referencia DATE NOT NULL
);
"""


def _safe_local_server(value: str) -> str:
    if value.lower() not in {"localhost", "127.0.0.1", ".", "(local)"}:
        raise SystemExit("equivalent_dev_requires_localhost")
    return value


def _safe_dev_database(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value) or not value.endswith("Dev"):
        raise SystemExit("equivalent_dev_requires_database_suffix_Dev")
    return value


def _driver() -> str:
    import pyodbc
    installed = set(pyodbc.drivers())
    for candidate in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if candidate in installed:
            return candidate
    raise RuntimeError("no_supported_sql_server_odbc_driver")


def _connect(server: str, database: str, *, autocommit: bool = False):
    import pyodbc
    driver = _driver()
    return pyodbc.connect(
        f"Driver={{{driver}}};Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
        timeout=10,
        autocommit=autocommit,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    return value


def _fingerprint(rows: Iterable[Iterable[Any]]) -> str:
    normalized = [[_json_value(v) for v in row] for row in rows]
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _create_database(server: str, database: str) -> None:
    conn = _connect(server, "master", autocommit=True)
    try:
        conn.cursor().execute(f"IF DB_ID('{database}') IS NULL CREATE DATABASE [{database}]")
    finally:
        conn.close()


def _execute_file(cursor, path: Path) -> None:
    cursor.execute(path.read_text(encoding="utf-8"))


def bootstrap(server: str, source_db: str, target_db: str) -> dict[str, Any]:
    _create_database(server, source_db)
    _create_database(server, target_db)

    source = _connect(server, source_db)
    try:
        cur = source.cursor()
        cur.execute(SOURCE_SCHEMA_SQL)
        for name, cfg in DATASETS.items():
            cur.execute(f"DELETE FROM legacy_ssrs.{name} WHERE data_referencia = ?", DATA_REFERENCIA)
            cols = ", ".join(cfg["columns"])
            marks = ", ".join("?" for _ in cfg["columns"])
            for row in cfg["rows"]:
                cur.execute(f"INSERT INTO legacy_ssrs.{name} ({cols}) VALUES ({marks})", *row)
        source.commit()
    except Exception:
        source.rollback()
        raise
    finally:
        source.close()

    target = _connect(server, target_db)
    try:
        cur = target.cursor()
        _execute_file(cur, DEV_SQL / "V1__source_schema.sql")
        for filename in (
            "V2__vw_prospeccao_movimento_fechamento_diario.sql",
            "V2__vw_prospeccao_movimento_pendencias_cadastro.sql",
            "V2__vw_prospeccao_movimento_pendencias_historicas.sql",
            "V2__vw_prospeccao_movimento_pendencias_observacao.sql",
        ):
            _execute_file(cur, VIEWS_SQL / filename)
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()

    return {
        "phase": "bootstrap",
        "status": "passed",
        "equivalent_source": True,
        "synthetic": True,
        "corporate_source_validated": False,
        "source_database": source_db,
        "target_database": target_db,
        "source_schema": "legacy_ssrs",
        "target_schema": "movimento_src",
        "data_referencia": DATA_REFERENCIA.isoformat(),
        "secrets_used": False,
        "production_touched": False,
    }


def _read_source(conn, dataset: str, columns: list[str]) -> list[tuple[Any, ...]]:
    cols = ", ".join(columns)
    cur = conn.cursor()
    cur.execute(
        f"SELECT {cols} FROM legacy_ssrs.{dataset} WHERE data_referencia = ? ORDER BY 1, 2",
        DATA_REFERENCIA,
    )
    return [tuple(row) for row in cur.fetchall()]


def _read_target(conn, dataset: str, columns: list[str]) -> list[tuple[Any, ...]]:
    cols = ", ".join(columns)
    cur = conn.cursor()
    cur.execute(
        f"SELECT {cols} FROM movimento_src.{dataset} "
        "WHERE source_tag = ? AND data_referencia = ? ORDER BY 1, 2",
        SOURCE_TAG,
        DATA_REFERENCIA,
    )
    return [tuple(row) for row in cur.fetchall()]


def sync(server: str, source_db: str, target_db: str) -> dict[str, Any]:
    source = _connect(server, source_db)
    target = _connect(server, target_db)
    dataset_evidence: dict[str, Any] = {}
    total_writes = 0
    try:
        all_equal = True
        source_rows_by_dataset: dict[str, list[tuple[Any, ...]]] = {}
        for name, cfg in DATASETS.items():
            src = _read_source(source, name, cfg["columns"])
            dst = _read_target(target, name, cfg["columns"])
            src_hash = _fingerprint(src)
            dst_hash = _fingerprint(dst)
            source_rows_by_dataset[name] = src
            equal = src_hash == dst_hash and len(src) == len(dst)
            all_equal = all_equal and equal
            dataset_evidence[name] = {
                "source_count": len(src),
                "target_count_before": len(dst),
                "source_sha256": src_hash,
                "target_sha256_before": dst_hash,
                "equal_before": equal,
            }

        if all_equal:
            action = "noop"
        else:
            cur = target.cursor()
            for name, cfg in DATASETS.items():
                cur.execute(
                    f"DELETE FROM movimento_src.{name} WHERE source_tag = ? AND data_referencia = ?",
                    SOURCE_TAG,
                    DATA_REFERENCIA,
                )
                cols = ", ".join([*cfg["columns"], "source_tag"])
                marks = ", ".join("?" for _ in [*cfg["columns"], "source_tag"])
                for row in source_rows_by_dataset[name]:
                    cur.execute(
                        f"INSERT INTO movimento_src.{name} ({cols}) VALUES ({marks})",
                        *row,
                        SOURCE_TAG,
                    )
                    total_writes += 1
            target.commit()
            action = "applied"

        for name, cfg in DATASETS.items():
            dst_after = _read_target(target, name, cfg["columns"])
            after_hash = _fingerprint(dst_after)
            dataset_evidence[name]["target_count_after"] = len(dst_after)
            dataset_evidence[name]["target_sha256_after"] = after_hash
            dataset_evidence[name]["equal_after"] = (
                after_hash == dataset_evidence[name]["source_sha256"]
                and len(dst_after) == dataset_evidence[name]["source_count"]
            )

        passed = all(v["equal_after"] for v in dataset_evidence.values())
        return {
            "phase": "sync",
            "status": "passed" if passed else "failed",
            "action": action,
            "already_present_no_write": action == "noop",
            "write_count": total_writes,
            "equivalent_source": True,
            "synthetic": True,
            "corporate_source_validated": False,
            "source_database": source_db,
            "target_database": target_db,
            "source_tag": SOURCE_TAG,
            "data_referencia": DATA_REFERENCIA.isoformat(),
            "datasets": dataset_evidence,
            "secrets_used": False,
            "production_touched": False,
        }
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def validate_views(server: str, target_db: str) -> dict[str, Any]:
    conn = _connect(server, target_db)
    counts: dict[str, int] = {}
    try:
        cur = conn.cursor()
        for name in DATASETS:
            cur.execute(
                f"SELECT COUNT(*) FROM dbo.vw_prospeccao_movimento_{name} WHERE data_referencia = ?",
                DATA_REFERENCIA,
            )
            counts[name] = int(cur.fetchone()[0])
    finally:
        conn.close()
    expected = {name: len(cfg["rows"]) for name, cfg in DATASETS.items()}
    passed = counts == expected
    return {
        "phase": "validate_views",
        "status": "passed" if passed else "failed",
        "counts": counts,
        "expected_counts": expected,
        "equivalent_source": True,
        "synthetic": True,
        "corporate_source_validated": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap", "sync", "validate", "run"))
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--source-db", default=SOURCE_DB_DEFAULT)
    parser.add_argument("--target-db", default=TARGET_DB_DEFAULT)
    args = parser.parse_args()

    server = _safe_local_server(args.server)
    source_db = _safe_dev_database(args.source_db)
    target_db = _safe_dev_database(args.target_db)

    if args.command == "bootstrap":
        result: Any = bootstrap(server, source_db, target_db)
    elif args.command == "sync":
        result = sync(server, source_db, target_db)
    elif args.command == "validate":
        result = validate_views(server, target_db)
    else:
        b = bootstrap(server, source_db, target_db)
        first = sync(server, source_db, target_db)
        second = sync(server, source_db, target_db)
        views = validate_views(server, target_db)
        passed = (
            b["status"] == "passed"
            and first["status"] == "passed"
            and first["action"] in {"applied", "noop"}
            and second["status"] == "passed"
            and second["action"] == "noop"
            and second["already_present_no_write"] is True
            and views["status"] == "passed"
        )
        result = {
            "status": "passed" if passed else "failed",
            "equivalent_source": True,
            "synthetic": True,
            "corporate_source_validated": False,
            "bootstrap": b,
            "first_sync": first,
            "repeat_sync": second,
            "view_validation": views,
            "secrets_used": False,
            "production_touched": False,
        }

    print(json.dumps(result, ensure_ascii=False, default=_json_value))
    return 0 if result.get("status") == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
