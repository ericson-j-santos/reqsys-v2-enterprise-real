#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ALLOWED_ENVIRONMENTS = {"dev", "stg", "prod"}
ALLOWED_ORIGINS = {
    "integrated-runtime",
    "post-merge-smoke",
    "environment-homologation",
}
CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
MAX_HISTORY = 30


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def verify_metadata(metadata: dict[str, Any], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []

    origin = metadata.get("origin")
    if origin not in ALLOWED_ORIGINS:
        reasons.append("origin_not_verified")

    environment = metadata.get("environment")
    if environment not in ALLOWED_ENVIRONMENTS:
        reasons.append("environment_not_verified")

    timestamp = _parse_timestamp(metadata.get("timestamp"))
    if timestamp is None:
        reasons.append("timestamp_not_verified")
    elif timestamp > now + timedelta(minutes=5):
        reasons.append("timestamp_in_future")

    correlation_id = metadata.get("correlation_id")
    if not isinstance(correlation_id, str) or not CORRELATION_PATTERN.fullmatch(correlation_id):
        reasons.append("correlation_id_not_verified")

    merge_sha = metadata.get("merge_sha")
    if not isinstance(merge_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        reasons.append("merge_sha_not_verified")

    return reasons


def normalize_evidence(
    report: dict[str, Any], metadata: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    reasons = verify_metadata(metadata, now=now)
    verified = not reasons
    return {
        "evidence_source": "runtime" if verified else "unverified",
        "verification_status": "verified" if verified else "rejected",
        "verification_reasons": reasons,
        "origin": metadata.get("origin"),
        "environment": metadata.get("environment"),
        "timestamp": metadata.get("timestamp"),
        "correlation_id": metadata.get("correlation_id"),
        "merge_sha": metadata.get("merge_sha"),
        "recovery_rate": float(report.get("recovery_rate", 0) or 0),
        "average_recovery_seconds": float(report.get("average_recovery_seconds", 0) or 0),
        "ux_100_ready": bool(report.get("ux_100_ready", False)),
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
    }


def ingest_history(
    history: list[dict[str, Any]] | None, evidence: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    history_out = [deepcopy(item) for item in (history or []) if isinstance(item, dict)]
    accepted = evidence.get("evidence_source") == "runtime"
    if accepted:
        duplicate = any(
            item.get("correlation_id") == evidence.get("correlation_id")
            and item.get("merge_sha") == evidence.get("merge_sha")
            for item in history_out
        )
        if not duplicate:
            history_out.append(deepcopy(evidence))
    audit = {
        "accepted": accepted,
        "duplicate": accepted and len(history_out) == len(history or []),
        "evidence_source": evidence.get("evidence_source"),
        "verification_status": evidence.get("verification_status"),
        "verification_reasons": evidence.get("verification_reasons", []),
        "history_size": min(len(history_out), MAX_HISTORY),
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
    }
    return history_out[-MAX_HISTORY:], audit


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    report = _read_json(args.report, {})
    metadata = _read_json(args.metadata, {})
    history = _read_json(args.history, [])
    evidence = normalize_evidence(
        report if isinstance(report, dict) else {},
        metadata if isinstance(metadata, dict) else {},
    )
    history_out, audit = ingest_history(
        history if isinstance(history, list) else [], evidence
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "runtime-evidence-normalized.json": evidence,
        "runtime-evidence-history.json": history_out,
        "runtime-evidence-ingestion-audit.json": audit,
    }
    for name, payload in outputs.items():
        (args.output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
