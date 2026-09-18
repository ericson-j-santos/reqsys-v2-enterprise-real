#!/usr/bin/env python3
"""Persist environment-promotion decisions and evaluate STG enforcement maturity."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_DECISIONS = {"approved", "approved_with_warning", "blocked", "insufficient_evidence"}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_history(previous: dict[str, Any], decision: dict[str, Any], limit: int = 180) -> dict[str, Any]:
    environment = str(decision.get("environment", "")).lower()
    status = str(decision.get("decision", ""))
    if environment not in {"dev", "stg", "prod"}:
        raise ValueError("environment must be dev, stg or prod")
    if status not in VALID_DECISIONS:
        raise ValueError(f"unsupported decision: {status}")

    points = list(previous.get("points") or [])
    point = {
        "recorded_at": decision.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "decision": status,
        "readiness_percent": decision.get("readiness_percent"),
        "metric_coverage_percent": decision.get("metric_coverage_percent"),
        "correlation_id": decision.get("correlation_id"),
        "run_id": decision.get("run_id"),
        "sha": decision.get("sha"),
    }
    dedupe_key = (point["environment"], point["run_id"], point["sha"], point["recorded_at"])
    existing = {
        (item.get("environment"), item.get("run_id"), item.get("sha"), item.get("recorded_at"))
        for item in points
    }
    if dedupe_key not in existing:
        points.append(point)
    points = sorted(points, key=lambda item: str(item.get("recorded_at", "")))[-limit:]

    stg = [item for item in points if item.get("environment") == "stg"]
    window = stg[-5:]
    valid = [item for item in window if item.get("decision") in {"approved", "approved_with_warning"}]
    approved = [item for item in window if item.get("decision") == "approved"]
    blocked = [item for item in window if item.get("decision") in {"blocked", "insufficient_evidence"}]
    ready = len(window) == 5 and len(valid) == 5 and len(approved) >= 4 and not blocked

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-environment-promotion-history",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "point_count": len(points),
        "points": points,
        "stg_enforcement_maturity": {
            "status": "ready_for_human_approval" if ready else "collecting_evidence",
            "automatic_change_allowed": False,
            "required_window": 5,
            "observed_window": len(window),
            "approved_count": len(approved),
            "valid_count": len(valid),
            "blocking_count": len(blocked),
            "criteria_met": ready,
            "next_action": "request_human_approval_to_enable_blocking" if ready else "collect_more_stg_executions",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_history(load(args.history), load(args.decision))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["stg_enforcement_maturity"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
