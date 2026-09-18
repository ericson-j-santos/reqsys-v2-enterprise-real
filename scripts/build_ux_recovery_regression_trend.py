#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
MAX_HISTORY = 30


def _card(dashboard: dict[str, Any]) -> dict[str, Any]:
    cards = dashboard.get("cards") if isinstance(dashboard.get("cards"), list) else []
    for item in cards:
        if isinstance(item, dict) and item.get("id") == "ux-recovery-standard-gold-readiness":
            return item
    raise ValueError("card ux-recovery-standard-gold-readiness não encontrado")


def evaluate(previous: list[dict[str, Any]] | None, dashboard: dict[str, Any], *, run_id: str, head_sha: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    current = _card(dashboard)
    history = [item for item in (previous or []) if isinstance(item, dict)]
    prior = history[-1] if history else None
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": str(run_id),
        "source_head_sha": head_sha,
        "generated_at": current.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "confidence_percent": int(current.get("confidence_percent", 0)),
        "recovery_rate_average": float(current.get("recovery_rate_average", 0)),
        "recovery_seconds_average": float(current.get("recovery_seconds_average", 0)),
        "consecutive_qualified_samples": int(current.get("consecutive_qualified_samples", 0)),
        "standard_gold_ready": current.get("standard_gold_ready") is True,
    }
    history = [item for item in history if str(item.get("source_run_id")) != str(run_id)]
    history.append(snapshot)
    history = history[-MAX_HISTORY:]

    alerts: list[str] = []
    deltas = {"confidence": 0, "recovery_rate": 0.0, "recovery_seconds": 0.0, "qualified_sequence": 0}
    if prior:
        deltas = {
            "confidence": snapshot["confidence_percent"] - int(prior.get("confidence_percent", 0)),
            "recovery_rate": round(snapshot["recovery_rate_average"] - float(prior.get("recovery_rate_average", 0)), 1),
            "recovery_seconds": round(snapshot["recovery_seconds_average"] - float(prior.get("recovery_seconds_average", 0)), 1),
            "qualified_sequence": snapshot["consecutive_qualified_samples"] - int(prior.get("consecutive_qualified_samples", 0)),
        }
        if deltas["recovery_rate"] < -5:
            alerts.append("recovery_rate_drop")
        if deltas["recovery_seconds"] > 5:
            alerts.append("recovery_time_increase")
        if deltas["qualified_sequence"] < 0:
            alerts.append("qualified_sequence_break")
        if deltas["confidence"] < -10:
            alerts.append("confidence_drop")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "UX_RECOVERY_REGRESSION_DETECTED" if alerts else "UX_RECOVERY_TREND_STABLE",
        "regression_detected": bool(alerts),
        "alerts": alerts,
        "deltas": deltas,
        "sample_count": len(history),
        "latest": snapshot,
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return history, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--history-output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    args = parser.parse_args()
    previous = []
    if args.previous and args.previous.exists():
        previous = json.loads(args.previous.read_text(encoding="utf-8"))
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    history, report = evaluate(previous, dashboard, run_id=args.run_id, head_sha=args.head_sha)
    args.history_output.parent.mkdir(parents=True, exist_ok=True)
    args.history_output.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "alerts": report["alerts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
