#!/usr/bin/env python3
"""Sincroniza a origem SQL corporativa para a camada canônica movimento_src em DEV.

A origem é estritamente leitura. O alvo precisa ser um banco DEV persistente.
Segredos entram por variável ou arquivo protegido no host e nunca são impressos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

OBJECT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")
SOURCE_TAG = "CORPORATE_SQL"
DEFAULT_MAPPING = {
    "fechamento_diario": {
        "source_object": "dbo.vw_prospeccao_movimento_fechamento_diario",
        "target_object": "movimento_src.fechamento_diario",
        "columns": ["indicador", "valor", "observacao", "data_referencia"],
        "view": "dbo.vw_prospeccao_movimento_fechamento_diario",
    },
    "pendencias_cadastro": {
        "source_object": "dbo.vw_prospeccao_movimento_pendencias_cadastro",
        "target_object": "movimento_src.pendencias_cadastro",
        "columns": ["protocolo", "cliente", "cpf", "pendencia", "dias_em_aberto", "responsavel", "data_referencia"],
        "view": "dbo.vw_prospeccao_movimento_pendencias_cadastro",
    },
    "pendencias_historicas": {
        "source_object": "dbo.vw_prospeccao_movimento_pendencias_historicas",
        "target_object": "movimento_src.pendencias_historicas",
        "columns": ["periodo_referencia", "pendencia", "quantidade", "percentual", "data_referencia"],
        "view": "dbo.vw_prospeccao_movimento_pendencias_historicas",
    },
    "pendencias_observacao": {
        "source_object": "dbo.vw_prospeccao_movimento_pendencias_observacao",
        "target_object": "movimento_src.pendencias_observacao",
        "columns": ["protocolo", "tipo_inconsistencia", "descricao", "etapa", "data_referencia"],
        "view": "dbo.vw_prospeccao_movimento_pendencias_observacao",
    },
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_secret(name: str) -> str:
    direct = os.getenv(name, "").strip()
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if direct and file_path:
        raise RuntimeError(f"{name}_ambiguous")
    if direct:
        return direct
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    raise RuntimeError(f"{name}_missing")


def dsn_value(dsn: str, key: str) -> str:
    wanted = key.casefold()
    for part in dsn.split(";"):
        if "=" not in part:
            continue
        k, value = part.split("=", 1)
        if k.strip().casefold() == wanted:
            return value.strip()
    return ""


def validate_source_dsn(dsn: str) -> None:
    encrypt = dsn_value(dsn, "Encrypt").casefold()
    trust = dsn_value(dsn, "TrustServerCertificate").casefold()
    if encrypt not in {"yes", "true", "mandatory", "strict"}:
        raise RuntimeError("source_dsn_requires_encrypt")
    if trust in {"yes", "true"}:
        raise RuntimeError("source_dsn_cannot_trust_server_certificate")


def load_mapping(path: Path | None) -> dict[str, dict[str, Any]]:
    payload: dict[str, Any] = DEFAULT_MAPPING if path is None else json.loads(path.read_text(encoding="utf-8"))
    datasets = payload.get("datasets", payload)
    if set(datasets) != set(DEFAULT_MAPPING):
        raise RuntimeError("mapping_dataset_contract_mismatch")
    normalized: dict[str, dict[str, Any]] = {}
    for name, item in datasets.items():
        source = str(item.get("source_object") or "").strip()
        target = str(item.get("target_object") or DEFAULT_MAPPING[name]["target_object"]).strip()
        view = str(item.get("view") or DEFAULT_MAPPING[name]["view"]).strip()
        columns = [str(x).strip() for x in item.get("columns") or []]
        if not all(OBJECT_RE.fullmatch(x) for x in (source, target, view)):
            raise RuntimeError(f"mapping_invalid_object:{name}")
        if columns != DEFAULT_MAPPING[name]["columns"]:
            raise RuntimeError(f"mapping_column_contract_mismatch:{name}")
        normalized[name] = {"source_object": source, "target_object": target, "view": view, "columns": columns}
    return normalized


def row_fingerprint(rows: Iterable[tuple[Any, ...]]) -> str:
    serial = json.dumps(
        [[None if value is None else str(value) for value in row] for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    )
    return sha256_text(serial)


def payload_fingerprint(dataset_hashes: dict[str, str], ref: str) -> str:
    return sha256_text(json.dumps({"date": ref, "datasets": dataset_hashes}, sort_keys=True, separators=(",", ":")))


def connect(dsn: str, *, autocommit: bool = False):
    import pyodbc
    return pyodbc.connect(dsn, timeout=20, autocommit=autocommit)


def source_metadata(conn) -> dict[str, str]:
    cur = conn.cursor()
    cur.execute("SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME()")
    server, database = cur.fetchone()
    return {
        "server_hash": sha256_text(str(server or ""))[:16],
        "database_hash": sha256_text(str(database or ""))[:16],
    }


def assert_target_dev(conn) -> str:
    cur = conn.cursor()
    cur.execute("SELECT DB_NAME()")
    database = str(cur.fetchone()[0] or "")
    if not database.casefold().endswith("dev"):
        raise RuntimeError("target_database_must_end_with_dev")
    return database


def validate_source_contract(conn, mapping: dict[str, dict[str, Any]]) -> None:
    cur = conn.cursor()
    for name, item in mapping.items():
        schema, obj = item["source_object"].split(".", 1)
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=? AND TABLE_NAME=? ORDER BY ORDINAL_POSITION",
            schema,
            obj,
        )
        actual = {str(row[0]) for row in cur.fetchall()}
        missing = [column for column in item["columns"] if column not in actual]
        if missing:
            raise RuntimeError(f"source_contract_missing:{name}:{','.join(missing)}")


def fetch_source_rows(conn, mapping: dict[str, dict[str, Any]], ref: date) -> dict[str, list[tuple[Any, ...]]]:
    cur = conn.cursor()
    result: dict[str, list[tuple[Any, ...]]] = {}
    for name, item in mapping.items():
        columns = ",".join(f"[{column}]" for column in item["columns"])
        cur.execute(
            f"SELECT {columns} FROM {item['source_object']} WHERE [data_referencia]=?",
            ref,
        )
        result[name] = [tuple(row) for row in cur.fetchall()]
    return result


AUDIT_SQL = """
IF SCHEMA_ID('movimento_ingest') IS NULL EXEC('CREATE SCHEMA movimento_ingest');
IF OBJECT_ID('movimento_ingest.runs','U') IS NULL
BEGIN
  CREATE TABLE movimento_ingest.runs(
    id bigint IDENTITY(1,1) PRIMARY KEY,
    correlation_id uniqueidentifier NOT NULL,
    data_referencia date NOT NULL,
    source_tag varchar(120) NOT NULL,
    payload_hash char(64) NOT NULL,
    status varchar(30) NOT NULL,
    row_counts_json nvarchar(max) NOT NULL,
    source_server_hash char(16) NOT NULL,
    source_database_hash char(16) NOT NULL,
    source_sha varchar(64) NULL,
    created_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
  );
  CREATE INDEX IX_movimento_ingest_scope
    ON movimento_ingest.runs(data_referencia, source_tag, status, id DESC);
END;
"""


def ensure_target_contract(conn, mapping: dict[str, dict[str, Any]]) -> None:
    cur = conn.cursor()
    cur.execute(AUDIT_SQL)
    for name, item in mapping.items():
        schema, obj = item["target_object"].split(".", 1)
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=? AND TABLE_NAME=?",
            schema,
            obj,
        )
        actual = {str(row[0]) for row in cur.fetchall()}
        expected = set(item["columns"]) | {"source_tag"}
        missing = sorted(expected - actual)
        if missing:
            raise RuntimeError(f"target_contract_missing:{name}:{','.join(missing)}")
    conn.commit()


def target_scope_fingerprint(conn, mapping: dict[str, dict[str, Any]], ref: date) -> str:
    cur = conn.cursor()
    hashes: dict[str, str] = {}
    for name, item in mapping.items():
        columns = ",".join(f"[{column}]" for column in item["columns"])
        cur.execute(
            f"SELECT {columns} FROM {item['target_object']} "
            "WHERE [source_tag]=? AND [data_referencia]=? ORDER BY [id]",
            SOURCE_TAG,
            ref,
        )
        hashes[name] = row_fingerprint(tuple(row) for row in cur.fetchall())
    return payload_fingerprint(hashes, ref.isoformat())


def previous_payload_hash(conn, ref: date) -> str:
    cur = conn.cursor()
    cur.execute(
        "SELECT TOP 1 payload_hash FROM movimento_ingest.runs "
        "WHERE data_referencia=? AND source_tag=? AND status IN ('applied','noop') ORDER BY id DESC",
        ref,
        SOURCE_TAG,
    )
    row = cur.fetchone()
    return str(row[0]) if row else ""


def apply_rows(conn, mapping: dict[str, dict[str, Any]], rows: dict[str, list[tuple[Any, ...]]], ref: date) -> None:
    cur = conn.cursor()
    for name, item in mapping.items():
        cur.execute(
            f"DELETE FROM {item['target_object']} WHERE [source_tag]=? AND [data_referencia]=?",
            SOURCE_TAG,
            ref,
        )
        if not rows[name]:
            continue
        insert_columns = item["columns"] + ["source_tag"]
        names = ",".join(f"[{column}]" for column in insert_columns)
        placeholders = ",".join("?" for _ in insert_columns)
        values = [tuple(row) + (SOURCE_TAG,) for row in rows[name]]
        cur.fast_executemany = True
        cur.executemany(f"INSERT INTO {item['target_object']}({names}) VALUES ({placeholders})", values)


def validate_views(conn, mapping: dict[str, dict[str, Any]], ref: date, expected: dict[str, int]) -> dict[str, int]:
    cur = conn.cursor()
    observed: dict[str, int] = {}
    for name, item in mapping.items():
        cur.execute(f"SELECT COUNT(*) FROM {item['view']} WHERE [data_referencia]=?", ref)
        observed[name] = int(cur.fetchone()[0])
        if observed[name] < expected[name]:
            raise RuntimeError(f"view_count_below_source:{name}")
    return observed


def record_run(conn, *, correlation_id: str, ref: date, payload_hash: str, status: str,
               counts: dict[str, int], metadata: dict[str, str], source_sha: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO movimento_ingest.runs("
        "correlation_id,data_referencia,source_tag,payload_hash,status,row_counts_json,"
        "source_server_hash,source_database_hash,source_sha"
        ") VALUES (?,?,?,?,?,?,?,?,?)",
        correlation_id,
        ref,
        SOURCE_TAG,
        payload_hash,
        status,
        json.dumps(counts, sort_keys=True),
        metadata["server_hash"],
        metadata["database_hash"],
        source_sha or None,
    )


def run(*, mode: str, ref: date, mapping_path: Path | None, evidence_path: Path,
        correlation_id: str, source_sha: str) -> int:
    source_dsn = read_secret("MOVIMENTO_EMAIL_SOURCE_DSN")
    target_dsn = read_secret("MOVIMENTO_EMAIL_TARGET_DSN")
    validate_source_dsn(source_dsn)
    mapping = load_mapping(mapping_path)

    source = connect(source_dsn)
    target = connect(target_dsn)
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "movimento_email_real_source_bridge",
        "environment": "dev",
        "captured_at": utcnow(),
        "correlation_id": correlation_id,
        "source_sha": source_sha,
        "mode": mode,
        "data_referencia": ref.isoformat(),
        "source_tag": SOURCE_TAG,
        "synthetic": False,
        "corporate_source_validated": False,
        "secret_exposed": False,
        "production_touched": False,
    }
    try:
        metadata = source_metadata(source)
        validate_source_contract(source, mapping)
        target_database = assert_target_dev(target)
        ensure_target_contract(target, mapping)
        rows = fetch_source_rows(source, mapping, ref)
        counts = {name: len(dataset) for name, dataset in rows.items()}
        dataset_hashes = {name: row_fingerprint(dataset) for name, dataset in rows.items()}
        overall_hash = payload_fingerprint(dataset_hashes, ref.isoformat())
        before = target_scope_fingerprint(target, mapping, ref)
        previous = previous_payload_hash(target, ref)

        if mode == "dry-run":
            after = target_scope_fingerprint(target, mapping, ref)
            if before != after:
                raise RuntimeError("dry_run_changed_target")
            status = "dry_run_passed"
            repeat_action = "no_write"
            observed = {}
        elif previous == overall_hash:
            observed = validate_views(target, mapping, ref, counts)
            record_run(
                target, correlation_id=correlation_id, ref=ref, payload_hash=overall_hash,
                status="noop", counts=counts, metadata=metadata, source_sha=source_sha,
            )
            target.commit()
            status = "noop"
            repeat_action = "already_present_no_write"
            after = target_scope_fingerprint(target, mapping, ref)
        else:
            apply_rows(target, mapping, rows, ref)
            observed = validate_views(target, mapping, ref, counts)
            record_run(
                target, correlation_id=correlation_id, ref=ref, payload_hash=overall_hash,
                status="applied", counts=counts, metadata=metadata, source_sha=source_sha,
            )
            target.commit()
            status = "applied"
            repeat_action = "write_applied"
            after = target_scope_fingerprint(target, mapping, ref)

        payload.update({
            "status": status,
            "corporate_source_validated": True,
            "source": metadata,
            "target_database_hash": sha256_text(target_database)[:16],
            "row_counts": counts,
            "business_data_observed": sum(counts.values()) > 0,
            "dataset_hashes": dataset_hashes,
            "payload_hash": overall_hash,
            "target_before_hash": before,
            "target_after_hash": after,
            "view_counts": observed,
            "repeat_action": repeat_action,
            "passed": True,
        })
        rc = 0
    except Exception as exc:
        target.rollback()
        payload.update({"status": "blocked", "passed": False, "error": str(exc).splitlines()[0][:240]})
        rc = 2
    finally:
        source.close()
        target.close()

    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "passed": payload["passed"],
        "synthetic": payload["synthetic"],
        "corporate_source_validated": payload["corporate_source_validated"],
        "row_counts": payload.get("row_counts", {}),
        "repeat_action": payload.get("repeat_action"),
        "error": payload.get("error"),
    }, ensure_ascii=False))
    return rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--data-referencia", required=True)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--source-sha", default=os.getenv("GITHUB_SHA", "").strip())
    args = parser.parse_args()
    correlation_id = args.correlation_id.strip() or str(uuid.uuid4())
    return run(
        mode=args.mode,
        ref=date.fromisoformat(args.data_referencia),
        mapping_path=args.mapping,
        evidence_path=args.evidence,
        correlation_id=correlation_id,
        source_sha=args.source_sha,
    )


if __name__ == "__main__":
    raise SystemExit(main())
