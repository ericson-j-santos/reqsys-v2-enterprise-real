#!/usr/bin/env python3
"""Fonte autogerida da Prospecção Movimento para DEV privado do ReqSys."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "owner" / "V1__owner_source_schema.sql"
TARGET_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "dev" / "V1__source_schema.sql"
VIEWS_SQL = ROOT / "backend" / "app" / "services" / "movimento_email" / "sql" / "views"

SOURCE_DB_DEFAULT = "ReqSysMovimentoOwnerDev"
TARGET_DB_DEFAULT = "ReqSysMovimentoDev"
SOURCE_TAG = "OWNER_MANAGED"
DATASETS = {
    "fechamento_diario": ["indicador", "valor", "observacao", "data_referencia"],
    "pendencias_cadastro": ["protocolo", "cliente", "cpf", "pendencia", "dias_em_aberto", "responsavel", "data_referencia"],
    "pendencias_historicas": ["periodo_referencia", "pendencia", "quantidade", "percentual", "data_referencia"],
    "pendencias_observacao": ["protocolo", "tipo_inconsistencia", "descricao", "etapa", "data_referencia"],
}


def _safe_local_server(value: str) -> str:
    if value.casefold() not in {"localhost", "127.0.0.1", ".", "(local)"}:
        raise RuntimeError("owner_source_requires_local_sql")
    return value


def _safe_dev_database(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value) or not value.endswith("Dev"):
        raise RuntimeError("owner_source_requires_Dev_database")
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
    return pyodbc.connect(
        f"Driver={{{_driver()}}};Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
        timeout=10,
        autocommit=autocommit,
    )


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _create_database(server: str, database: str) -> None:
    conn = _connect(server, "master", autocommit=True)
    try:
        conn.cursor().execute(f"IF DB_ID('{database}') IS NULL CREATE DATABASE [{database}]")
    finally:
        conn.close()


def _execute_sql_file(cursor, path: Path) -> None:
    cursor.execute(path.read_text(encoding="utf-8"))


def bootstrap(server: str, source_db: str, target_db: str) -> dict[str, Any]:
    server = _safe_local_server(server)
    source_db = _safe_dev_database(source_db)
    target_db = _safe_dev_database(target_db)
    _create_database(server, source_db)
    _create_database(server, target_db)

    source = _connect(server, source_db)
    try:
        _execute_sql_file(source.cursor(), SCHEMA_SQL)
        source.commit()
    finally:
        source.close()

    target = _connect(server, target_db)
    try:
        cur = target.cursor()
        _execute_sql_file(cur, TARGET_SQL)
        for filename in (
            "V2__vw_prospeccao_movimento_fechamento_diario.sql",
            "V2__vw_prospeccao_movimento_pendencias_cadastro.sql",
            "V2__vw_prospeccao_movimento_pendencias_historicas.sql",
            "V2__vw_prospeccao_movimento_pendencias_observacao.sql",
        ):
            _execute_sql_file(cur, VIEWS_SQL / filename)
        target.commit()
    finally:
        target.close()

    return {
        "status": "passed",
        "source_authority": "owner_managed",
        "synthetic": False,
        "source_database": source_db,
        "target_database": target_db,
        "secrets_used": False,
        "production_touched": False,
    }


def _normalize_payload(payload: dict[str, Any]) -> tuple[dt.date, dict[str, list[list[Any]]]]:
    ref = dt.date.fromisoformat(str(payload.get("data_referencia") or ""))
    datasets = payload.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != set(DATASETS):
        raise RuntimeError("owner_payload_dataset_contract_mismatch")
    normalized: dict[str, list[list[Any]]] = {}
    for name, columns in DATASETS.items():
        rows = datasets.get(name)
        if not isinstance(rows, list):
            raise RuntimeError(f"owner_payload_rows_invalid:{name}")
        out: list[list[Any]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(columns):
                raise RuntimeError(f"owner_payload_columns_invalid:{name}")
            values = [row[column] for column in columns]
            if str(row["data_referencia"]) != ref.isoformat():
                raise RuntimeError(f"owner_payload_reference_mismatch:{name}")
            out.append(values)
        normalized[name] = out
    return ref, normalized


def ingest(server: str, source_db: str, payload_path: Path, correlation_id: str) -> dict[str, Any]:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ref, datasets = _normalize_payload(payload)
    payload_hash = _sha(payload)
    source = _connect(_safe_local_server(server), _safe_dev_database(source_db))
    counts: dict[str, int] = {}
    try:
        cur = source.cursor()
        cur.execute(
            "SELECT TOP 1 payload_hash,status FROM owner_movimento.ingest_runs "
            "WHERE data_referencia=? ORDER BY id DESC",
            ref,
        )
        previous = cur.fetchone()
        if previous and str(previous[0]) == payload_hash and str(previous[1]) == "applied":
            return {
                "status": "noop",
                "source_authority": "owner_managed",
                "payload_hash": payload_hash,
                "data_referencia": ref.isoformat(),
                "write_count": 0,
                "secrets_used": False,
                "production_touched": False,
            }

        for name, columns in DATASETS.items():
            cur.execute(f"DELETE FROM owner_movimento.{name} WHERE data_referencia=?", ref)
            rows = datasets[name]
            counts[name] = len(rows)
            if not rows:
                continue
            names = ",".join(f"[{column}]" for column in columns) + ",[source_record_hash]"
            marks = ",".join("?" for _ in range(len(columns) + 1))
            for row in rows:
                cur.execute(
                    f"INSERT INTO owner_movimento.{name}({names}) VALUES ({marks})",
                    *row,
                    _sha({"dataset": name, "row": row}),
                )
        cur.execute(
            "INSERT INTO owner_movimento.ingest_runs("
            "correlation_id,data_referencia,payload_hash,row_counts_json,status"
            ") VALUES (?,?,?,?,?)",
            correlation_id,
            ref,
            payload_hash,
            json.dumps(counts, sort_keys=True),
            "applied",
        )
        source.commit()
    except Exception:
        source.rollback()
        raise
    finally:
        source.close()

    return {
        "status": "applied",
        "source_authority": "owner_managed",
        "payload_hash": payload_hash,
        "data_referencia": ref.isoformat(),
        "row_counts": counts,
        "write_count": sum(counts.values()),
        "secrets_used": False,
        "production_touched": False,
    }


def sync(server: str, source_db: str, target_db: str, ref: dt.date) -> dict[str, Any]:
    source = _connect(_safe_local_server(server), _safe_dev_database(source_db))
    target = _connect(_safe_local_server(server), _safe_dev_database(target_db))
    writes = 0
    counts: dict[str, int] = {}
    try:
        src_cur = source.cursor()
        dst_cur = target.cursor()
        for name, columns in DATASETS.items():
            cols = ",".join(f"[{c}]" for c in columns)
            src_cur.execute(f"SELECT {cols} FROM dbo.vw_prospeccao_movimento_{name} WHERE data_referencia=? ORDER BY 1", ref)
            rows = [tuple(row) for row in src_cur.fetchall()]
            counts[name] = len(rows)

            dst_cur.execute(
                f"SELECT {cols} FROM movimento_src.{name} "
                "WHERE source_tag=? AND data_referencia=? ORDER BY 1",
                SOURCE_TAG,
                ref,
            )
            current = [tuple(row) for row in dst_cur.fetchall()]
            if _sha(rows) == _sha(current) and len(rows) == len(current):
                continue
            dst_cur.execute(
                f"DELETE FROM movimento_src.{name} WHERE source_tag=? AND data_referencia=?",
                SOURCE_TAG,
                ref,
            )
            insert_names = ",".join([*(f"[{c}]" for c in columns), "[source_tag]"])
            marks = ",".join("?" for _ in range(len(columns) + 1))
            for row in rows:
                dst_cur.execute(
                    f"INSERT INTO movimento_src.{name}({insert_names}) VALUES ({marks})",
                    *row,
                    SOURCE_TAG,
                )
                writes += 1
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    return {
        "status": "noop" if writes == 0 else "applied",
        "source_authority": "owner_managed",
        "synthetic": False,
        "data_referencia": ref.isoformat(),
        "row_counts": counts,
        "write_count": writes,
        "already_present_no_write": writes == 0,
        "secrets_used": False,
        "production_touched": False,
    }


def validate(server: str, source_db: str, target_db: str) -> dict[str, Any]:
    source = _connect(_safe_local_server(server), _safe_dev_database(source_db))
    target = _connect(_safe_local_server(server), _safe_dev_database(target_db))
    try:
        src_cur = source.cursor()
        dst_cur = target.cursor()
        source_objects: dict[str, bool] = {}
        target_objects: dict[str, bool] = {}
        for name in DATASETS:
            src_cur.execute("SELECT CASE WHEN OBJECT_ID(?, 'V') IS NULL THEN 0 ELSE 1 END", f"dbo.vw_prospeccao_movimento_{name}")
            source_objects[name] = bool(src_cur.fetchone()[0])
            dst_cur.execute("SELECT CASE WHEN OBJECT_ID(?, 'V') IS NULL THEN 0 ELSE 1 END", f"dbo.vw_prospeccao_movimento_{name}")
            target_objects[name] = bool(dst_cur.fetchone()[0])
    finally:
        source.close()
        target.close()
    passed = all(source_objects.values()) and all(target_objects.values())
    return {
        "status": "passed" if passed else "blocked",
        "source_authority": "owner_managed",
        "synthetic": False,
        "source_objects": source_objects,
        "target_objects": target_objects,
        "secrets_used": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap", "ingest", "sync", "validate"))
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--source-db", default=SOURCE_DB_DEFAULT)
    parser.add_argument("--target-db", default=TARGET_DB_DEFAULT)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--data-referencia")
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args()

    correlation_id = args.correlation_id.strip() or f"movimento-owner-{uuid.uuid4()}"
    if args.command == "bootstrap":
        result = bootstrap(args.server, args.source_db, args.target_db)
    elif args.command == "ingest":
        if not args.input:
            raise SystemExit("--input_required")
        result = ingest(args.server, args.source_db, args.input, correlation_id)
    elif args.command == "sync":
        if not args.data_referencia:
            raise SystemExit("--data-referencia_required")
        result = sync(args.server, args.source_db, args.target_db, dt.date.fromisoformat(args.data_referencia))
    else:
        result = validate(args.server, args.source_db, args.target_db)

    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result["status"] in {"passed", "applied", "noop"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
