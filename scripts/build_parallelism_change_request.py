#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build(policy: dict[str, Any]) -> dict[str, Any]:
    current_stage = int(policy["current_stage"])
    recommended_stage = int(policy["recommended_stage"])
    decision = str(policy["decision"])

    if recommended_stage > current_stage:
        request_status = "AWAITING_HUMAN_APPROVAL"
        change_type = "INCREASE_ONE_STAGE"
    elif recommended_stage < current_stage:
        request_status = "ROLLBACK_RECOMMENDED"
        change_type = "DECREASE_ONE_STAGE"
    else:
        request_status = "NO_CHANGE"
        change_type = "KEEP_LIMITS"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-parallelism-change-request",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_contract": policy.get("contract"),
        "source_of_truth": policy.get("source_of_truth"),
        "decision": decision,
        "reason": policy.get("reason"),
        "current_stage": current_stage,
        "recommended_stage": recommended_stage,
        "change_type": change_type,
        "request_status": request_status,
        "approval": {
            "required": True,
            "approved": False,
            "approved_by": None,
            "approved_at": None,
        },
        "execution": {
            "automatic_application_allowed": False,
            "applied": False,
            "applied_by": None,
            "applied_at": None,
        },
        "production": {
            "promotion_allowed": False,
        },
        "rollback": {
            "required_on_instability": bool(policy.get("rollback_on_instability", True)),
            "recommended": recommended_stage < current_stage,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build(json.loads(args.policy.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"request_status": result["request_status"], "change_type": result["change_type"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
