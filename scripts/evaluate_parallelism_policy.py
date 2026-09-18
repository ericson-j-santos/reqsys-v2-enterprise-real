#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_STABLE_WINDOWS = 3
MAX_STAGE = 3


def evaluate(history: list[dict[str, Any]], current_stage: int) -> dict[str, Any]:
    recent = history[-MIN_STABLE_WINDOWS:]
    stable_windows = sum(
        1
        for item in recent
        if item.get("parallelism_decision") == "INCREASE_SAFE"
        and item.get("status") == "STABLE"
        and item.get("risk") == "low"
    )
    all_recent_stable = len(recent) == MIN_STABLE_WINDOWS and stable_windows == MIN_STABLE_WINDOWS

    latest = history[-1] if history else {}
    latest_stable = (
        latest.get("parallelism_decision") == "INCREASE_SAFE"
        and latest.get("status") == "STABLE"
        and latest.get("risk") == "low"
    )

    if not latest_stable:
        decision = "KEEP_LIMITS"
        recommended_stage = max(0, current_stage - 1)
        reason = "latest_window_not_stable"
    elif all_recent_stable and current_stage < MAX_STAGE:
        decision = "INCREASE_ONE_STAGE"
        recommended_stage = current_stage + 1
        reason = "three_consecutive_stable_windows"
    else:
        decision = "KEEP_LIMITS"
        recommended_stage = current_stage
        reason = "stability_window_not_complete_or_max_stage_reached"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-staged-parallelism-policy",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_stage": current_stage,
        "recommended_stage": recommended_stage,
        "maximum_stage": MAX_STAGE,
        "required_consecutive_stable_windows": MIN_STABLE_WINDOWS,
        "observed_windows": len(recent),
        "stable_windows": stable_windows,
        "decision": decision,
        "reason": reason,
        "automatic_application_allowed": False,
        "human_approval_required": True,
        "promotion_allowed": False,
        "rollback_on_instability": True,
        "source_of_truth": "reqsys-parallelism-effect-index",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--current-stage", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    history = json.loads(args.history.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        raise SystemExit("history must be a JSON array")
    if args.current_stage < 0 or args.current_stage > MAX_STAGE:
        raise SystemExit(f"current stage must be between 0 and {MAX_STAGE}")

    result = evaluate(history, args.current_stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "recommended_stage": result["recommended_stage"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
