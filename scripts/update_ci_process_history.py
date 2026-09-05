#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def history_record(analytics: dict[str, Any]) -> dict[str, Any]:
    comparison = analytics.get("baseline_comparison") or {}
    window_comparability = analytics.get("window_comparability") or {}
    return {
        "schema_version": "1.0.1",
        "generated_at": analytics.get("generated_at"),
        "run_id": analytics.get("run_id"),
        "status": analytics.get("status"),
        "completed_runs": analytics.get("completed_runs", 0),
        "current": {
            "success_rate_percent": analytics.get("success_rate_percent", 0),
            "failure_rate_percent": analytics.get("failure_rate_percent", 0),
            "first_pass_success_rate_percent": analytics.get("first_pass_success_rate_percent", 0),
            "rerun_rate_percent": analytics.get("rerun_rate_percent", 0),
            "avg_seconds": analytics.get("avg_seconds", 0),
            "p50_seconds": analytics.get("p50_seconds", 0),
            "p95_seconds": analytics.get("p95_seconds", 0),
            "stddev_seconds": analytics.get("stddev_seconds", 0),
            "cv_percent": analytics.get("cv_percent", 0),
            "p95_queue_seconds": analytics.get("p95_queue_seconds", 0),
        },
        "baseline_comparison": {
            "available": bool(comparison.get("available")),
            "overall_signal": comparison.get("overall_signal"),
            "delta": comparison.get("delta", {}),
            "mode": comparison.get("mode", "report-only"),
            "creates_gate": bool(comparison.get("creates_gate", False)),
        },
        "window_comparability": {
            "available": bool(window_comparability.get("available")),
            "comparable_to_baseline": bool(window_comparability.get("comparable_to_baseline")),
            "reason_codes": list(window_comparability.get("reason_codes") or []),
            "ratios": window_comparability.get("ratios", {}),
            "current_sample": window_comparability.get("current_sample", {}),
            "baseline_sample": window_comparability.get("baseline_sample"),
            "mode": window_comparability.get("mode", "descriptive-only"),
            "creates_gate": bool(window_comparability.get("creates_gate", False)),
        },
    }


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def merge_history(records: list[dict[str, Any]], record: dict[str, Any], max_records: int = 180) -> list[dict[str, Any]]:
    key = str(record.get("run_id") or record.get("generated_at"))
    deduped = {str(item.get("run_id") or item.get("generated_at")): item for item in records}
    deduped[key] = record
    ordered = sorted(deduped.values(), key=lambda item: str(item.get("generated_at") or ""))
    return ordered[-max_records:]


def write_history(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records), encoding="utf-8")


def main() -> int:
    analytics_path = Path(os.environ.get("CI_ANALYTICS_PATH", "audit/ci-lead-time-analytics.json"))
    history_path = Path(os.environ.get("CI_PROCESS_HISTORY_PATH", "audit/history/ci-process-improvement-history.jsonl"))
    max_records = int(os.environ.get("CI_PROCESS_HISTORY_MAX_RECORDS", "180"))
    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    records = merge_history(load_history(history_path), history_record(analytics), max_records=max_records)
    write_history(history_path, records)
    print(json.dumps({"history_path": str(history_path), "records": len(records), "latest_run_id": records[-1].get("run_id") if records else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
