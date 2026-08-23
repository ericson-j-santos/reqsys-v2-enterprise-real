#!/usr/bin/env python3
"""Build an auditable human approval record for STG enforcement."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_DECISIONS = {"approve", "reject"}
EXPECTED_HISTORY_CONTRACT = "reqsys-environment-promotion-history"
HUMAN_APPROVAL_MODE = "human_workflow_dispatch"


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
    approver_type: str,
    rationale: str,
    ticket: str,
    source_pr_number: str,
    source_run_id: str,
    source_sha: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    decision = decision.strip().lower()
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"decision must be one of: {sorted(ALLOWED_DECISIONS)}")

    maturity = history.get("stg_enforcement_maturity") or {}
    maturity_status = maturity.get("status")
    required_window = maturity.get("required_window")
    observed_window = maturity.get("observed_window")
    approved_count = maturity.get("approved_count")
    valid_count = maturity.get("valid_count")
    blocking_count = maturity.get("blocking_count")
    canonical_history = history.get("contract") == EXPECTED_HISTORY_CONTRACT
    canonical_window = (
        isinstance(required_window, int)
        and not isinstance(required_window, bool)
        and required_window > 0
        and isinstance(observed_window, int)
        and not isinstance(observed_window, bool)
        and observed_window >= required_window
        and isinstance(approved_count, int)
        and not isinstance(approved_count, bool)
        and approved_count >= required_window - 1
        and isinstance(valid_count, int)
        and not isinstance(valid_count, bool)
        and valid_count >= required_window
        and isinstance(blocking_count, int)
        and not isinstance(blocking_count, bool)
        and blocking_count == 0
    )
    evidence_ready = (
        canonical_history
        and maturity_status == "ready_for_human_approval"
        and maturity.get("criteria_met") is True
        and maturity.get("automatic_change_allowed") is False
        and canonical_window
    )

    approver = normalize_text(approver, "approver")
    approver_type = normalize_text(approver_type, "approver_type", minimum=1)
    rationale = normalize_text(rationale, "rationale", minimum=10)
    ticket = normalize_text(ticket, "ticket")
    source_pr_number = normalize_text(source_pr_number, "source_pr_number", minimum=1)
    source_run_id = normalize_text(source_run_id, "source_run_id", minimum=1)
    source_sha = normalize_text(source_sha, "source_sha", minimum=7)
    actor = approver.removeprefix("github:")
    if not approver.startswith("github:") or not actor or actor.lower().endswith("[bot]"):
        raise ValueError("approver must identify an authenticated human GitHub actor")
    if approver_type != "User":
        raise ValueError("approver_type must be User")
    if not source_pr_number.isdigit():
        raise ValueError("source_pr_number must be numeric")
    if not source_run_id.isdigit():
        raise ValueError("source_run_id must be numeric")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_sha):
        raise ValueError("source_sha must be a full 40-character Git SHA")
    if ticket.upper() == "REQSYS-TEMP-AUTO-APPROVAL":
        raise ValueError("temporary automated approval tickets are not accepted")

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
        "approver_type": approver_type,
        "ticket": ticket,
        "source_pr_number": source_pr_number,
        "source_run_id": source_run_id,
        "source_sha": source_sha,
        "maturity_status": maturity_status,
        "generated_at": timestamp,
    }
    correlation_id = "stg-approval-" + hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]

    return {
        "schema_version": "1.1.0",
        "contract": "reqsys-stg-enforcement-approval",
        "generated_at": timestamp,
        "correlation_id": correlation_id,
        "status": status,
        "requested_decision": decision,
        "effective_approval": effective,
        "approval_mode": HUMAN_APPROVAL_MODE,
        "automatic_policy_change": False,
        "automatic_deploy": False,
        "approval": {
            "approver": approver,
            "actor_type": approver_type,
            "rationale": rationale,
            "ticket": ticket,
        },
        "evidence": {
            "maturity_status": maturity_status,
            "ready_for_human_approval": evidence_ready,
            "history_contract_valid": canonical_history,
            "criteria_met": maturity.get("criteria_met") is True,
            "automatic_change_allowed": maturity.get("automatic_change_allowed"),
            "source_pr_number": int(source_pr_number),
            "source_run_id": source_run_id,
            "source_sha": source_sha,
            "required_stg_window": required_window,
            "observed_stg_window": observed_window,
            "approved_count": approved_count,
            "valid_count": valid_count,
            "blocking_count": blocking_count,
        },
        "next_action": (
            "authorize_bound_policy_pr"
            if effective
            else "preserve_current_policy_and_collect_evidence"
            if status == "blocked_by_evidence"
            else "preserve_current_policy"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--approver-type", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--source-pr-number", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    record = build_record(
        history=load_object(args.history),
        decision=args.decision,
        approver=args.approver,
        approver_type=args.approver_type,
        rationale=args.rationale,
        ticket=args.ticket,
        source_pr_number=args.source_pr_number,
        source_run_id=args.source_run_id,
        source_sha=args.source_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "correlation_id": record["correlation_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
