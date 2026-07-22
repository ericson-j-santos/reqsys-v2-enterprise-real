#!/usr/bin/env python3
"""Validate a governed STG enforcement approval artifact against policy change context."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CONTRACT = "reqsys-stg-enforcement-approval"
EXPECTED_STATUS = "approved_for_policy_change"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate(approval: dict[str, Any], expected_sha: str, expected_run_id: str | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    approval_details = approval.get("approval") or {}
    evidence = approval.get("evidence") or {}

    if not approval:
        reasons.append("approval_artifact_missing")
    if approval.get("contract") != EXPECTED_CONTRACT:
        reasons.append("approval_contract_invalid")
    if approval.get("status") != EXPECTED_STATUS:
        reasons.append("approval_status_invalid")
    if str(approval.get("requested_decision") or "").lower() != "approve":
        reasons.append("approval_decision_invalid")
    if approval.get("effective_approval") is not True:
        reasons.append("approval_not_effective")
    if not str(approval_details.get("approver") or "").strip():
        reasons.append("approval_actor_missing")
    if not str(approval_details.get("rationale") or "").strip():
        reasons.append("approval_justification_missing")
    if not str(approval_details.get("ticket") or "").strip():
        reasons.append("approval_ticket_missing")

    approved_sha = str(evidence.get("source_sha") or "")
    if approved_sha != expected_sha:
        reasons.append("approval_sha_mismatch")
    approved_run = str(evidence.get("source_run_id") or "")
    if expected_run_id and approved_run != str(expected_run_id):
        reasons.append("approval_run_id_mismatch")
    if not str(approval.get("correlation_id") or "").strip():
        reasons.append("approval_correlation_id_missing")

    valid = not reasons
    fingerprint_source = json.dumps(approval, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "schema_version": "1.0.1",
        "contract": "reqsys-stg-policy-approval-validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid": valid,
        "decision": "authorized" if valid else "blocked",
        "expected_sha": expected_sha,
        "expected_run_id": expected_run_id,
        "approval_fingerprint_sha256": hashlib.sha256(fingerprint_source).hexdigest(),
        "approval_correlation_id": approval.get("correlation_id"),
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-run-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = validate(load_json(args.approval), args.expected_sha, args.expected_run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"]}))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
