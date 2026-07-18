#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_TARGETS = {"worker", "queue", "api"}
ALLOWED_ENVIRONMENTS = {"dev", "stg"}


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AdapterResult:
    state: dict[str, Any]
    receipt: dict[str, Any]


def _validate_execution(execution: dict[str, Any]) -> None:
    if execution.get("contract") != "reqsys-parallelism-execution-receipt":
        raise ValueError("invalid execution receipt contract")
    if execution.get("status") not in {"APPLIED", "ROLLED_BACK"}:
        raise ValueError("unsupported execution status")
    if execution.get("guardrails", {}).get("non_production_only") is not True:
        raise ValueError("non-production guardrail is required")
    if execution.get("guardrails", {}).get("production_promotion_allowed") is not False:
        raise ValueError("production promotion must remain blocked")
    unsigned = dict(execution)
    expected = unsigned.pop("execution_sha256", None)
    if expected != hashlib.sha256(canonical(unsigned)).hexdigest():
        raise ValueError("execution receipt checksum mismatch")


def apply_adapter(
    state: dict[str, Any],
    execution: dict[str, Any],
    *,
    target: str,
    environment: str,
    expected_version: int,
    smoke_healthy: bool,
    actor: str,
) -> AdapterResult:
    normalized_target = target.strip().lower()
    normalized_environment = environment.strip().lower()
    normalized_actor = actor.strip()

    if normalized_target not in ALLOWED_TARGETS:
        raise ValueError("unsupported target")
    if normalized_environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("production and unknown environments are blocked")
    if not normalized_actor:
        raise ValueError("actor is required")
    _validate_execution(execution)
    if execution.get("environment") != normalized_environment:
        raise ValueError("execution environment mismatch")

    if state.get("contract") != "reqsys-parallelism-target-state":
        raise ValueError("invalid target state contract")
    if state.get("target") != normalized_target or state.get("environment") != normalized_environment:
        raise ValueError("target state identity mismatch")
    if bool(state.get("validation_pending")):
        raise ValueError("target has pending validation")
    if int(state.get("version", -1)) != expected_version:
        raise ValueError("compare-and-swap version mismatch")

    execution_sha = str(execution["execution_sha256"])
    applied_receipts = list(state.get("applied_execution_receipts", []))
    if execution_sha in applied_receipts:
        return AdapterResult(
            state=state,
            receipt={
                "contract": "reqsys-parallelism-target-adapter-receipt",
                "schema_version": "1.0.0",
                "status": "IDEMPOTENT_NOOP",
                "target": normalized_target,
                "environment": normalized_environment,
                "execution_sha256": execution_sha,
                "version": state["version"],
                "production_promotion_allowed": False,
            },
        )

    previous_stage = int(state.get("stage", 0))
    requested_stage = int(execution["change"]["target_stage"])
    if abs(requested_stage - previous_stage) > 1:
        raise ValueError("adapter change exceeds one stage")

    now = datetime.now(timezone.utc).isoformat()
    candidate = dict(state)
    candidate.update(
        stage=requested_stage,
        version=expected_version + 1,
        validation_pending=True,
        updated_at=now,
        updated_by=normalized_actor,
        last_execution_sha256=execution_sha,
    )

    rolled_back = not smoke_healthy
    if rolled_back:
        candidate.update(
            stage=previous_stage,
            version=expected_version + 2,
            validation_pending=False,
            rollback_reason="post-change smoke failed",
            rollback_at=now,
        )
        status = "ROLLED_BACK"
    else:
        candidate["validation_pending"] = False
        applied_receipts.append(execution_sha)
        candidate["applied_execution_receipts"] = applied_receipts
        status = "APPLIED"

    receipt = {
        "schema_version": "1.0.0",
        "contract": "reqsys-parallelism-target-adapter-receipt",
        "generated_at": now,
        "status": status,
        "target": normalized_target,
        "environment": normalized_environment,
        "actor": normalized_actor,
        "execution_sha256": execution_sha,
        "compare_and_swap": {
            "expected_version": expected_version,
            "result_version": candidate["version"],
        },
        "change": {
            "previous_stage": previous_stage,
            "requested_stage": requested_stage,
            "effective_stage": candidate["stage"],
        },
        "smoke": {"healthy": smoke_healthy},
        "rollback": {"executed": rolled_back},
        "idempotency": {"key": execution_sha},
        "validation_pending": candidate["validation_pending"],
        "production_promotion_allowed": False,
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical(receipt)).hexdigest()
    return AdapterResult(state=candidate, receipt=receipt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=sorted(ALLOWED_TARGETS))
    parser.add_argument("--environment", required=True, choices=sorted(ALLOWED_ENVIRONMENTS))
    parser.add_argument("--expected-version", required=True, type=int)
    parser.add_argument("--smoke-healthy", required=True, choices=["true", "false"])
    parser.add_argument("--actor", required=True)
    parser.add_argument("--state-output", required=True, type=Path)
    parser.add_argument("--receipt-output", required=True, type=Path)
    args = parser.parse_args()

    result = apply_adapter(
        json.loads(args.state.read_text(encoding="utf-8")),
        json.loads(args.execution.read_text(encoding="utf-8")),
        target=args.target,
        environment=args.environment,
        expected_version=args.expected_version,
        smoke_healthy=args.smoke_healthy == "true",
        actor=args.actor,
    )
    args.state_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.state_output.write_text(json.dumps(result.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.receipt_output.write_text(json.dumps(result.receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.receipt["status"], "target": args.target, "stage": result.state["stage"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
