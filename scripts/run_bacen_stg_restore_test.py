#!/usr/bin/env python3
"""Executa backup e restauração reais em PostgreSQL isolado e gera evidência BACEN-04.

O teste usa exclusivamente bancos efêmeros identificados por prefixo controlado. PROD é
bloqueado por validação explícita. As credenciais são recebidas por variáveis de ambiente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ALLOWED_ENVIRONMENT = "stg-isolated"
DB_PREFIX = "reqsys_bacen_stg_"
FIXTURE_SETUP_SQL = (
    "CREATE TABLE bacen_restore_fixture (id integer PRIMARY KEY, payload text NOT NULL);"
    "INSERT INTO bacen_restore_fixture "
    "SELECT n, md5('reqsys-bacen-' || n::text) "
    "FROM generate_series(1, 1000) AS n;"
)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def run(command: list[str], *, database: str | None = None, capture: bool = False) -> str:
    env = os.environ.copy()
    if database:
        env["PGDATABASE"] = database
    try:
        result = subprocess.run(
            command,
            check=True,
            env=env,
            text=True,
            capture_output=capture,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or "sem saída adicional"
        raise RuntimeError(f"comando falhou ({command[0]}): {detail}") from exc
    return result.stdout.strip() if capture else ""


def scalar(sql: str, database: str) -> str:
    return run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-Atc", sql],
        database=database,
        capture=True,
    )


def validate_database_name(name: str) -> None:
    if not name.startswith(DB_PREFIX):
        raise ValueError(f"banco fora do prefixo isolado permitido: {name}")
    if "prod" in name.lower():
        raise ValueError("qualquer referência a PROD é proibida neste teste")


def build_integrity_snapshot(database: str) -> dict[str, str | int]:
    count = int(scalar("SELECT count(*) FROM bacen_restore_fixture;", database))
    digest = scalar(
        "SELECT md5(string_agg(id::text || ':' || payload, '|' ORDER BY id)) "
        "FROM bacen_restore_fixture;",
        database,
    )
    return {"row_count": count, "content_digest": digest}


def execute(output: Path, asset_id: str) -> dict[str, object]:
    environment = os.getenv("BACEN_RESTORE_ENVIRONMENT", ALLOWED_ENVIRONMENT)
    if environment != ALLOWED_ENVIRONMENT:
        raise ValueError(f"ambiente inválido: {environment}")

    suffix = uuid.uuid4().hex[:10]
    source_db = f"{DB_PREFIX}source_{suffix}"
    target_db = f"{DB_PREFIX}target_{suffix}"
    validate_database_name(source_db)
    validate_database_name(target_db)

    output.parent.mkdir(parents=True, exist_ok=True)
    backup_file = output.parent / f"{source_db}.dump"
    correlation_id = str(uuid.uuid4())
    started_at = utc_now()

    try:
        run(["createdb", source_db])
        run(
            ["psql", "-v", "ON_ERROR_STOP=1", "-c", FIXTURE_SETUP_SQL],
            database=source_db,
        )
        source_snapshot = build_integrity_snapshot(source_db)

        run(["pg_dump", "--format=custom", "--file", str(backup_file), source_db])
        if not backup_file.is_file() or backup_file.stat().st_size == 0:
            raise RuntimeError("pg_dump não produziu um arquivo de backup válido")
        backup_created_at = utc_now()
        backup_sha256 = hashlib.sha256(backup_file.read_bytes()).hexdigest()

        restore_started_at = utc_now()
        start = time.monotonic()
        run(["createdb", target_db])
        run(["pg_restore", "--exit-on-error", "--dbname", target_db, str(backup_file)])
        elapsed_seconds = time.monotonic() - start
        restore_completed_at = utc_now()

        target_snapshot = build_integrity_snapshot(target_db)
        integrity_match = source_snapshot == target_snapshot
        rpo_minutes = max(0, int((restore_started_at - backup_created_at).total_seconds() // 60))
        rto_seconds = round(elapsed_seconds, 3)
        result = "passed" if integrity_match and rpo_minutes <= 1440 and rto_seconds <= 14400 else "failed"

        evidence: dict[str, object] = {
            "schema_version": "2.0.1",
            "control_id": "BACEN-04",
            "evidence_class": "isolated_stg_restore_test",
            "environment": environment,
            "production_restore_claimed": False,
            "production_touched": False,
            "asset_id": asset_id,
            "source_database": source_db,
            "target_database": target_db,
            "backup_id": backup_file.name,
            "backup_created_at": backup_created_at.isoformat(),
            "restore_started_at": restore_started_at.isoformat(),
            "restore_completed_at": restore_completed_at.isoformat(),
            "rpo_minutes": rpo_minutes,
            "rto_seconds": rto_seconds,
            "rpo_target_minutes": 1440,
            "rto_target_seconds": 14400,
            "backup_sha256": backup_sha256,
            "source_integrity": source_snapshot,
            "restored_integrity": target_snapshot,
            "integrity_match": integrity_match,
            "correlation_id": correlation_id,
            "result": result,
            "executed_by": "github-actions",
            "reviewed_by": "automated-policy",
            "commit_sha": os.getenv("GITHUB_SHA", "local"),
            "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "started_at": started_at.isoformat(),
            "generated_at": utc_now().isoformat(),
        }
        output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if result != "passed":
            raise RuntimeError("teste de restauração não atingiu os critérios BACEN-04")
        return evidence
    finally:
        for database in (target_db, source_db):
            subprocess.run(["dropdb", "--if-exists", database], env=os.environ.copy(), check=False)
        backup_file.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", default="reqsys-postgresql-stg-isolated")
    parser.add_argument(
        "--output",
        default="artifacts/bacen/bacen-04-stg-restore-evidence.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence = execute(Path(args.output), args.asset_id)
    print(json.dumps({"result": evidence["result"], "correlation_id": evidence["correlation_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
