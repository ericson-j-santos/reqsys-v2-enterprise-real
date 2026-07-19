#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def build(parallelism: dict[str, Any], runtime: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    metrics = parallelism.get("metrics", {})
    runtime_status = runtime.get("status") or runtime.get("overall_status") or "unknown"
    quality_status = quality.get("status") or quality.get("overall_status") or "unknown"

    ci_stable = parallelism.get("status") == "STABLE"
    runtime_green = str(runtime_status).lower() in {"green", "healthy", "success", "ready", "stable"}
    quality_green = str(quality_status).lower() in {"green", "healthy", "success", "passed", "stable"}
    evidence_complete = bool(parallelism) and bool(runtime) and bool(quality)

    if evidence_complete and ci_stable and runtime_green and quality_green:
        status, risk = "EXECUTIVE_GREEN", "low"
    elif evidence_complete:
        status, risk = "EXECUTIVE_ATTENTION", "moderate"
    else:
        status, risk = "EVIDENCE_INCOMPLETE", "moderate"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-unified-executive-integration-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "risk": risk,
        "indicators": {
            "throughput": {
                "merged_pull_requests": parallelism.get("window", {}).get("merged_pull_requests"),
                "decision": parallelism.get("parallelism_decision"),
            },
            "lead_time": {
                "average_minutes": metrics.get("average_lead_time_minutes"),
            },
            "ci_stability": {
                "stable": ci_stable,
                "rerun_rate_percent": metrics.get("rerun_rate_percent"),
                "merge_queue_success_rate_percent": metrics.get("merge_queue_success_rate_percent"),
            },
            "quality": {
                "status": quality_status,
            },
            "runtime": {
                "status": runtime_status,
            },
        },
        "evidence": {
            "parallelism_present": bool(parallelism),
            "runtime_present": bool(runtime),
            "quality_present": bool(quality),
            "complete": evidence_complete,
        },
        "production": {
            "promotion_allowed": False,
            "human_approval_required": True,
        },
        "next_safe_action": "KEEP_LIMITS_AND_REVIEW" if status != "EXECUTIVE_GREEN" else "HUMAN_REVIEW_FOR_ONE_STAGE_INCREASE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parallelism", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--quality", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(load(args.parallelism), load(args.runtime), load(args.quality))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "risk": result["risk"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
