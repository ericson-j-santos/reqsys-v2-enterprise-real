#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

CARD_ID = "empty-state-recovery-trend"
KEY = "user_experience_empty_state_recovery_trend"


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def evaluate(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    pending: dict[str, list[datetime]] = defaultdict(list)
    durations: dict[str, list[float]] = defaultdict(list)
    views = recoveries = 0
    ordered = sorted(
        [e for e in (events or []) if isinstance(e, dict) and _dt(e.get("occurredAt"))],
        key=lambda e: _dt(e["occurredAt"]),
    )
    for event in ordered:
        context = str(event.get("context", "unknown"))[:80]
        when = _dt(event.get("occurredAt"))
        kind = event.get("event")
        if when is None:
            continue
        if kind == "view":
            pending[context].append(when)
            views += 1
        elif kind in {"primary_action", "secondary_action"} and pending[context]:
            started = pending[context].pop(0)
            durations[context].append(max(0.0, (when - started).total_seconds()))
            recoveries += 1
    all_durations = [value for values in durations.values() for value in values]
    avg_seconds = round(mean(all_durations), 1) if all_durations else 0.0
    recovery_rate = round((recoveries / views) * 100, 1) if views else 0.0
    by_context = {
        context: {
            "recoveries": len(values),
            "average_seconds": round(mean(values), 1),
        }
        for context, values in sorted(durations.items())
    }
    criteria = {
        "minimum_views": views >= 5,
        "recovery_rate_at_least_60": recovery_rate >= 60,
        "average_recovery_at_most_30s": bool(all_durations) and avg_seconds <= 30,
        "smoke_required": True,
        "human_approval_required": True,
    }
    ux_100_ready = all(criteria[name] for name in (
        "minimum_views", "recovery_rate_at_least_60", "average_recovery_at_most_30s"
    ))
    return {
        "id": CARD_ID,
        "title": "Tendência de recuperação de estados vazios",
        "status": "UX_100_EVIDENCE_READY" if ux_100_ready else "UX_RECOVERY_TRENDING",
        "views": views,
        "recoveries": recoveries,
        "recovery_rate": recovery_rate,
        "average_recovery_seconds": avg_seconds,
        "by_context": by_context,
        "ux_100_ready": ux_100_ready,
        "criteria": criteria,
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def consolidate(dashboard: dict[str, Any], history: list[dict[str, Any]], report: dict[str, Any]):
    dashboard_out = deepcopy(dashboard)
    cards = dashboard_out.get("cards", [])
    cards = cards if isinstance(cards, list) else []
    dashboard_out["cards"] = [c for c in cards if not (isinstance(c, dict) and c.get("id") == CARD_ID)] + [report]
    history_out = [item for item in history if isinstance(item, dict)]
    history_out.append({
        "generated_at": report["generated_at"],
        "recovery_rate": report["recovery_rate"],
        "average_recovery_seconds": report["average_recovery_seconds"],
        "ux_100_ready": report["ux_100_ready"],
    })
    return dashboard_out, history_out[-30:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    telemetry = json.loads(args.telemetry.read_text(encoding="utf-8"))
    events = telemetry if isinstance(telemetry, list) else telemetry.get("events", [])
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history.exists() else []
    report = evaluate(events)
    dashboard_out, history_out = consolidate(dashboard, history, report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("empty-state-recovery-trend.json", report),
        ("ops-dashboard.json", dashboard_out),
        ("empty-state-recovery-history.json", history_out),
    ):
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
