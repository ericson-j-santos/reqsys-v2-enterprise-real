#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ENVIRONMENTS = {"dev", "stg"}
ALLOWED_ACTIONS = {"APPLY", "ROLLBACK"}


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("contract") != "reqsys-parallelism-approval-receipt":
        raise ValueError("invalid approval receipt contract")
    if receipt.get("schema_version") != "1.0.0":
        raise ValueError("unsupported approval receipt schema_version")
    if receipt.get("decision_status") != "APPROVED":
        raise ValueError("approval receipt is not approved")
    if receipt.get("approval", {}).get("approved") is not True:
        raise ValueError("approval flag is required")
    if receipt.get("execution", {}).get("automatic_application_allowed") is not False:
        raise ValueError("automatic application invariant violated")
    if receipt.get("production", {}).get("promotion_allowed") is not False:
        raise ValueError("production promotion invariant violated")

    expected = receipt.get("receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError("approval receipt checksum mismatch")


def _validate_metrics(metrics: dict[str, Any]) -> None:
    if metrics.get("contract") != "reqsys-parallelism-effect-index":
        raise ValueError("invalid metrics contract")
    if metrics.get("stable") is not True:
        raise ValueError("metrics are unstable")
    if int(metrics.get("stable_windows", 0)) < 3:
        raise ValueError("three stable windows are required")
    if float(metrics.get("error_rate", 1.0)) > float(metrics.get("max_error_rate", 0.02)):
        raise ValueError("error rate exceeds governed threshold")


def build_execution(
    receipt: dict[str, Any],
    metrics: dict[str, Any],
    *,
    environment: str,
    action: str,
    actor: str,
) -> dict[str, Any]:
    normalized_environment = environment.strip().lower()
    normalized_action = action.strip().upper()
    normalized_actor = actor.strip()

    if normalized_environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("production and unknown environments are blocked")
    if normalized_action not in ALLOWED_ACTIONS:
        raise ValueError("unsupported execution action")
    if not normalized_actor:
        raise ValueError("actor is required")

    _verify_receipt(receipt)
    _validate_metrics(metrics)

    current_stage = int(receipt["change"]["current_stage"])
    approved_stage = int(receipt["change"]["recommended_stage"])
    if abs(approved_stage - current_stage) != 1:
        raise ValueError("only one-stage changes are allowed")

    target_stage = approved_stage if normalized_action == "APPLY" else current_stage
    previous_stage = current_stage if normalized_action == "APPLY" else approved_stage
    generated_at = datetime.now(timezone.utc).isoformat()

    result = {
        "schema_version": "1.0.0",
        "contract": "reqsys-parallelism-execution-receipt",
        "generated_at": generated_at,
        "environment": normalized_environment,
        "action": normalized_action,
        "status": "APPLIED" if normalized_action == "APPLY" else "ROLLED_BACK",
        "actor": normalized_actor,
        "change": {
            "previous_stage": previous_stage,
            "target_stage": target_stage,
            "delta": target_stage - previous_stage,
            "maximum_stage_delta": 1,
        },
        "source": {
            "approval_receipt_sha256": receipt["receipt_sha256"],
            "metrics_sha256": hashlib.sha256(_canonical(metrics)).hexdigest(),
        },
        "validation": {
            "stable": True,
            "stable_windows": int(metrics["stable_windows"]),
            "error_rate": float(metrics["error_rate"]),
        },
        "guardrails": {
            "non_production_only": True,
            "production_promotion_allowed": False,
            "automatic_rollback_required_on_instability": True,
        },
    }
    result["execution_sha256"] = hashlib.sha256(_canonical(result)).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--environment", required=True, choices=sorted(ALLOWED_ENVIRONMENTS))
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build_execution(
        json.loads(args.receipt.read_text(encoding="utf-8")),
        json.loads(args.metrics.read_text(encoding="utf-8")),
        environment=args.environment,
        action=args.action,
        actor=args.actor,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "target_stage": result["change"]["target_stage"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
