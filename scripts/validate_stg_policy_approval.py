#!/usr/bin/env python3
"""Validate a governed STG approval artifact against its exact authorized scope."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CONTRACT = "reqsys-stg-enforcement-approval"
EXPECTED_APPROVAL_MODE = "human_workflow_dispatch"
EXPECTED_STATUSES = {
    "policy_change": "approved_for_policy_change",
    "exception_retirement": "approved_for_exception_retirement",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate(
    approval: dict[str, Any],
    expected_sha: str,
    expected_run_id: str | None = None,
    expected_pr_number: str | None = None,
    expected_scope: str = "policy_change",
) -> dict[str, Any]:
    reasons: list[str] = []
    approval_details = approval.get("approval") or {}
    evidence = approval.get("evidence") or {}
    if expected_scope not in EXPECTED_STATUSES:
        raise ValueError(f"unsupported expected_scope: {expected_scope}")

    if not approval:
        reasons.append("approval_artifact_missing")
    if approval.get("contract") != EXPECTED_CONTRACT:
        reasons.append("approval_contract_invalid")
    if approval.get("status") != EXPECTED_STATUSES[expected_scope]:
        reasons.append("approval_status_invalid")
    if approval.get("approval_scope") != expected_scope:
        reasons.append("approval_scope_mismatch")
    if str(approval.get("requested_decision") or "").lower() != "approve":
        reasons.append("approval_decision_invalid")
    if approval.get("effective_approval") is not True:
        reasons.append("approval_not_effective")
    if approval.get("approval_mode") != EXPECTED_APPROVAL_MODE:
        reasons.append("approval_mode_not_human_dispatch")
    if approval.get("automatic_policy_change") is not False:
        reasons.append("automatic_policy_change_not_disabled")
    if approval.get("automatic_deploy") is not False:
        reasons.append("automatic_deploy_not_disabled")

    approver = str(approval_details.get("approver") or "").strip()
    actor = approver.removeprefix("github:")
    if not approver:
        reasons.append("approval_actor_missing")
    elif not approver.startswith("github:") or not actor or actor.lower().endswith("[bot]"):
        reasons.append("approval_actor_not_authenticated_human")
    if approval_details.get("actor_type") != "User":
        reasons.append("approval_actor_type_not_user")
    if len(str(approval_details.get("rationale") or "").strip()) < 10:
        reasons.append("approval_justification_missing")
    ticket = str(approval_details.get("ticket") or "").strip()
    if not ticket:
        reasons.append("approval_ticket_missing")
    elif ticket.upper() == "REQSYS-TEMP-AUTO-APPROVAL":
        reasons.append("approval_ticket_temporary_automation")

    if evidence.get("history_contract_valid") is not True:
        reasons.append("approval_history_contract_invalid")
    if evidence.get("automatic_change_allowed") is not False:
        reasons.append("approval_evidence_allows_automatic_change")
    if expected_scope == "policy_change":
        if evidence.get("maturity_status") != "ready_for_human_approval":
            reasons.append("approval_maturity_not_ready")
        if evidence.get("ready_for_human_approval") is not True:
            reasons.append("approval_evidence_not_ready")
        if evidence.get("criteria_met") is not True:
            reasons.append("approval_criteria_not_met")
        if evidence.get("policy_change_ready") is not True:
            reasons.append("approval_policy_change_evidence_invalid")
    else:
        if evidence.get("maturity_status") not in {
            "ready_for_human_approval",
            "collecting_evidence",
        }:
            reasons.append("approval_retirement_maturity_invalid")
        if evidence.get("exception_retirement_evidence_valid") is not True:
            reasons.append("approval_retirement_evidence_invalid")

    approved_sha = str(evidence.get("source_sha") or "")
    if approved_sha != expected_sha:
        reasons.append("approval_sha_mismatch")
    approved_run = str(evidence.get("source_run_id") or "")
    if not approved_run.isdigit():
        reasons.append("approval_source_run_id_invalid")
    if expected_run_id and approved_run != str(expected_run_id):
        reasons.append("approval_run_id_mismatch")
    approved_pr = str(evidence.get("source_pr_number") or "")
    if not approved_pr.isdigit():
        reasons.append("approval_source_pr_number_invalid")
    if expected_pr_number and approved_pr != str(expected_pr_number):
        reasons.append("approval_pr_number_mismatch")
    if not str(approval.get("correlation_id") or "").strip():
        reasons.append("approval_correlation_id_missing")

    valid = not reasons
    fingerprint_source = json.dumps(approval, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "schema_version": "1.2.0",
        "contract": "reqsys-stg-policy-approval-validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid": valid,
        "decision": "authorized" if valid else "blocked",
        "expected_sha": expected_sha,
        "expected_run_id": expected_run_id,
        "expected_pr_number": expected_pr_number,
        "expected_scope": expected_scope,
        "approval_fingerprint_sha256": hashlib.sha256(fingerprint_source).hexdigest(),
        "approval_correlation_id": approval.get("correlation_id"),
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-run-id")
    parser.add_argument("--expected-pr-number")
    parser.add_argument("--expected-scope", choices=sorted(EXPECTED_STATUSES), default="policy_change")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = validate(
        load_json(args.approval),
        args.expected_sha,
        args.expected_run_id,
        args.expected_pr_number,
        args.expected_scope,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"]}))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
