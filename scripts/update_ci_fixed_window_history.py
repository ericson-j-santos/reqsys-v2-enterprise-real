#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from update_ci_process_history import history_record as legacy_history_record, load_history, write_history


def history_record(analytics: dict[str, Any]) -> dict[str, Any]:
    record = legacy_history_record(analytics)
    window = analytics.get("collection_window") or {}
    record["schema_version"] = "1.0.2"
    record["collection_window"] = {
        "policy_id": window.get("policy_id"),
        "window_id": window.get("window_id"),
        "mode": window.get("mode"),
        "duration_minutes": window.get("duration_minutes"),
        "settle_minutes": window.get("settle_minutes"),
        "anchor_minute": window.get("anchor_minute"),
        "start_at": window.get("start_at"),
        "end_at": window.get("end_at"),
        "min_completed_runs": window.get("min_completed_runs"),
        "min_completion_coverage_percent": window.get("min_completion_coverage_percent"),
        "runs_in_window": window.get("runs_in_window"),
        "completed_runs": window.get("completed_runs"),
        "incomplete_runs": window.get("incomplete_runs"),
        "completion_coverage_percent": window.get("completion_coverage_percent"),
        "collection_complete": bool(window.get("collection_complete")),
        "sample_eligible": bool(window.get("sample_eligible")),
        "eligibility_reason_codes": list(window.get("eligibility_reason_codes") or []),
        "creates_gate": False,
    }
    return record


def _key(item: dict[str, Any]) -> str:
    window = item.get("collection_window") or {}
    if window.get("mode") == "fixed_time" and window.get("window_id"):
        return f"fixed:{window['window_id']}"
    return str(item.get("run_id") or item.get("generated_at"))


def merge_history(records: list[dict[str, Any]], record: dict[str, Any], max_records: int = 180) -> list[dict[str, Any]]:
    deduped = {_key(item): item for item in records}
    deduped[_key(record)] = record
    ordered = sorted(deduped.values(), key=lambda item: str(item.get("generated_at") or ""))
    return ordered[-max_records:]


def main() -> int:
    analytics_path = Path(os.environ.get("CI_ANALYTICS_PATH", "audit/ci-lead-time-analytics.json"))
    history_path = Path(os.environ.get("CI_PROCESS_HISTORY_PATH", "audit/history/ci-process-improvement-history.jsonl"))
    max_records = int(os.environ.get("CI_PROCESS_HISTORY_MAX_RECORDS", "180"))
    analytics = json.loads(analytics_path.read_text(encoding="utf-8"))
    records = merge_history(load_history(history_path), history_record(analytics), max_records=max_records)
    write_history(history_path, records)
    print(json.dumps({
        "history_path": str(history_path),
        "records": len(records),
        "latest_run_id": records[-1].get("run_id") if records else None,
        "latest_window_id": (records[-1].get("collection_window") or {}).get("window_id") if records else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
