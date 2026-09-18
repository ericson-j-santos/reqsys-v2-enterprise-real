#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_DECISIONS = {"APPROVE", "REJECT"}


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build(
    request: dict[str, Any],
    *,
    decision: str,
    actor: str,
    reason: str,
    source_artifact_id: str,
    repository: str,
    run_id: str,
) -> dict[str, Any]:
    normalized_decision = decision.strip().upper()
    normalized_actor = actor.strip()
    normalized_reason = reason.strip()

    if normalized_decision not in ALLOWED_DECISIONS:
        raise ValueError(f"unsupported decision: {normalized_decision}")
    if not normalized_actor:
        raise ValueError("actor is required")
    if not normalized_reason:
        raise ValueError("reason is required")
    if request.get("contract") != "reqsys-parallelism-change-request":
        raise ValueError("invalid change request contract")
    if request.get("schema_version") != "1.0.0":
        raise ValueError("unsupported change request schema_version")
    if request.get("execution", {}).get("automatic_application_allowed") is not False:
        raise ValueError("automatic application must remain disabled")
    if request.get("production", {}).get("promotion_allowed") is not False:
        raise ValueError("production promotion must remain disabled")
    if normalized_decision == "APPROVE" and request.get("request_status") != "AWAITING_HUMAN_APPROVAL":
        raise ValueError("only pending increase requests can be approved")

    approved = normalized_decision == "APPROVE"
    generated_at = datetime.now(timezone.utc).isoformat()
    request_sha256 = hashlib.sha256(_canonical_json(request)).hexdigest()

    receipt = {
        "schema_version": "1.0.0",
        "contract": "reqsys-parallelism-approval-receipt",
        "generated_at": generated_at,
        "decision": normalized_decision,
        "decision_status": "APPROVED" if approved else "REJECTED",
        "reason": normalized_reason,
        "actor": normalized_actor,
        "source": {
            "repository": repository,
            "artifact_id": str(source_artifact_id),
            "workflow_run_id": str(run_id),
            "change_request_sha256": request_sha256,
            "change_request_contract": request.get("contract"),
            "change_request_status": request.get("request_status"),
        },
        "change": {
            "current_stage": request.get("current_stage"),
            "recommended_stage": request.get("recommended_stage"),
            "change_type": request.get("change_type"),
        },
        "approval": {
            "required": True,
            "approved": approved,
            "approved_by": normalized_actor if approved else None,
            "approved_at": generated_at if approved else None,
        },
        "execution": {
            "automatic_application_allowed": False,
            "applied": False,
            "requires_separate_workflow": True,
        },
        "production": {
            "promotion_allowed": False,
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(_canonical_json(receipt)).hexdigest()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--decision", required=True, choices=sorted(ALLOWED_DECISIONS))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--source-artifact-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    request = json.loads(args.request.read_text(encoding="utf-8"))
    receipt = build(
        request,
        decision=args.decision,
        actor=args.actor,
        reason=args.reason,
        source_artifact_id=args.source_artifact_id,
        repository=args.repository,
        run_id=args.run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision_status": receipt["decision_status"], "receipt_sha256": receipt["receipt_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
