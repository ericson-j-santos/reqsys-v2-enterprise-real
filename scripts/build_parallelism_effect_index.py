#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def _minutes(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    a = datetime.fromisoformat(start.replace("Z", "+00:00"))
    b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return round((b - a).total_seconds() / 60, 2)


def build(prs: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    merged = [pr for pr in prs if pr.get("merged_at")]
    lead_times = [value for pr in merged if (value := _minutes(pr.get("created_at"), pr.get("merged_at"))) is not None]
    conflicts = sum(1 for pr in prs if pr.get("mergeable") is False or pr.get("mergeable_state") == "dirty")

    completed = [run for run in runs if run.get("status") == "completed"]
    reruns = [run for run in completed if int(run.get("run_attempt") or 1) > 1]
    queue_runs = [run for run in completed if run.get("event") == "merge_group" or "Merge Queue" in str(run.get("name", ""))]
    queue_success = [run for run in queue_runs if run.get("conclusion") == "success"]

    rerun_rate = round(len(reruns) / len(completed) * 100, 2) if completed else 0.0
    conflict_rate = round(conflicts / len(prs) * 100, 2) if prs else 0.0
    queue_success_rate = round(len(queue_success) / len(queue_runs) * 100, 2) if queue_runs else 0.0
    lead_time_avg = round(mean(lead_times), 2) if lead_times else None

    stable = (
        len(merged) >= 5
        and rerun_rate <= 15
        and conflict_rate <= 10
        and len(queue_runs) >= 3
        and queue_success_rate >= 90
    )
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-parallelism-effect-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"pull_requests": len(prs), "merged_pull_requests": len(merged), "workflow_runs": len(completed)},
        "metrics": {
            "average_lead_time_minutes": lead_time_avg,
            "rerun_rate_percent": rerun_rate,
            "conflict_rate_percent": conflict_rate,
            "merge_queue_success_rate_percent": queue_success_rate,
            "merge_queue_samples": len(queue_runs),
        },
        "thresholds": {
            "minimum_merged_prs": 5,
            "maximum_rerun_rate_percent": 15,
            "maximum_conflict_rate_percent": 10,
            "minimum_merge_queue_samples": 3,
            "minimum_merge_queue_success_rate_percent": 90,
        },
        "status": "STABLE" if stable else "OBSERVATION_REQUIRED",
        "parallelism_decision": "INCREASE_SAFE" if stable else "KEEP_LIMITS",
        "risk": "low" if stable else "moderate",
        "promotion_allowed": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prs", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(json.loads(args.prs.read_text()), json.loads(args.runs.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "decision": result["parallelism_decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
