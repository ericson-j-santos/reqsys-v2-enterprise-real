#!/usr/bin/env python3
"""Gera evidência determinística do controle BACEN-04 para validação de CI/STG.

Este script não declara que um backup produtivo real foi restaurado. Ele valida o
contrato de evidência e produz um artifact de teste explicitamente identificado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ALLOWED_ENVIRONMENTS = {"ci", "dev", "stg"}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def build_evidence(environment: str, asset_id: str) -> dict[str, object]:
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError(f"environment inválido: {environment}")
    if not asset_id.strip():
        raise ValueError("asset_id é obrigatório")

    completed_at = utc_now()
    started_at = completed_at - timedelta(seconds=2)
    backup_created_at = completed_at - timedelta(minutes=30)
    payload = f"{environment}:{asset_id}:{backup_created_at.isoformat()}".encode()
    digest = hashlib.sha256(payload).hexdigest()

    evidence: dict[str, object] = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-04",
        "evidence_class": "contract_validation",
        "production_restore_claimed": False,
        "environment": environment,
        "asset_id": asset_id,
        "backup_id": f"contract-{digest[:16]}",
        "backup_created_at": backup_created_at.isoformat(),
        "restore_started_at": started_at.isoformat(),
        "restore_completed_at": completed_at.isoformat(),
        "rpo_minutes": 30,
        "rto_minutes": 1,
        "integrity_sha256": digest,
        "correlation_id": str(uuid.uuid5(uuid.NAMESPACE_URL, digest)),
        "result": "passed",
        "executed_by": "github-actions",
        "reviewed_by": "pending_operational_review",
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "generated_at": completed_at.isoformat(),
    }
    validate_evidence(evidence)
    return evidence


def validate_evidence(evidence: dict[str, object]) -> None:
    required = {
        "schema_version",
        "control_id",
        "environment",
        "asset_id",
        "backup_id",
        "backup_created_at",
        "restore_started_at",
        "restore_completed_at",
        "rpo_minutes",
        "rto_minutes",
        "integrity_sha256",
        "correlation_id",
        "result",
        "executed_by",
        "reviewed_by",
    }
    missing = sorted(required.difference(evidence))
    if missing:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(missing)}")
    if evidence["control_id"] != "BACEN-04":
        raise ValueError("control_id deve ser BACEN-04")
    if evidence["result"] != "passed":
        raise ValueError("resultado da evidência deve ser passed")
    digest = str(evidence["integrity_sha256"])
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("integrity_sha256 inválido")
    uuid.UUID(str(evidence["correlation_id"]))
    for field in ("backup_created_at", "restore_started_at", "restore_completed_at"):
        datetime.fromisoformat(str(evidence[field]))
    if int(evidence["rpo_minutes"]) > 1440:
        raise ValueError("RPO excede 24 horas")
    if int(evidence["rto_minutes"]) > 240:
        raise ValueError("RTO excede 4 horas")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", default="ci", choices=sorted(ALLOWED_ENVIRONMENTS))
    parser.add_argument("--asset-id", default="reqsys-bacen-contract-fixture")
    parser.add_argument("--output", default="artifacts/bacen/bacen-04-backup-restore-evidence.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = build_evidence(args.environment, args.asset_id)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"result": "passed", "output": str(output), "control_id": "BACEN-04"}))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"result": "failed", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
