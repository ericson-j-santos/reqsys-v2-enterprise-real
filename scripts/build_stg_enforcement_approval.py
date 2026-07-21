#!/usr/bin/env python3
"""Build an auditable human approval record for STG enforcement."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_DECISIONS = {"approve", "reject"}


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def normalize_text(value: str, field: str, minimum: int = 3) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} characters")
    return normalized


def build_record(
    history: dict[str, Any],
    decision: str,
    approver: str,
    rationale: str,
    ticket: str,
    source_run_id: str,
    source_sha: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    decision = decision.strip().lower()
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"decision must be one of: {sorted(ALLOWED_DECISIONS)}")

    maturity = history.get("stg_maturity") or {}
    maturity_status = maturity.get("status")
    evidence_ready = maturity_status == "ready_for_human_approval"

    approver = normalize_text(approver, "approver")
    rationale = normalize_text(rationale, "rationale", minimum=10)
    ticket = normalize_text(ticket, "ticket")
    source_run_id = normalize_text(source_run_id, "source_run_id", minimum=1)
    source_sha = normalize_text(source_sha, "source_sha", minimum=7)

    effective = decision == "approve" and evidence_ready
    status = (
        "approved_for_policy_change"
        if effective
        else "rejected"
        if decision == "reject"
        else "blocked_by_evidence"
    )
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()

    canonical = {
        "decision": decision,
        "approver": approver,
        "ticket": ticket,
        "source_run_id": source_run_id,
        "source_sha": source_sha,
        "maturity_status": maturity_status,
        "generated_at": timestamp,
    }
    correlation_id = "stg-approval-" + hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-stg-enforcement-approval",
        "generated_at": timestamp,
        "correlation_id": correlation_id,
        "status": status,
        "requested_decision": decision,
        "effective_approval": effective,
        "automatic_policy_change": False,
        "automatic_deploy": False,
        "approval": {
            "approver": approver,
            "rationale": rationale,
            "ticket": ticket,
        },
        "evidence": {
            "maturity_status": maturity_status,
            "ready_for_human_approval": evidence_ready,
            "source_run_id": source_run_id,
            "source_sha": source_sha,
            "observed_stg_window": maturity.get("window_size"),
            "approved_count": maturity.get("approved_count"),
            "blocked_count": maturity.get("blocked_count"),
            "insufficient_evidence_count": maturity.get("insufficient_evidence_count"),
        },
        "next_action": (
            "open_policy_change_pr"
            if effective
            else "preserve_warning_only_and_collect_evidence"
            if status == "blocked_by_evidence"
            else "preserve_warning_only"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    record = build_record(
        history=load_object(args.history),
        decision=args.decision,
        approver=args.approver,
        rationale=args.rationale,
        ticket=args.ticket,
        source_run_id=args.source_run_id,
        source_sha=args.source_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "correlation_id": record["correlation_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
