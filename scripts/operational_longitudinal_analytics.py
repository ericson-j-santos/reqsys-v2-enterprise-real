#!/usr/bin/env python3
"""Longitudinal operational analytics from persisted history snapshots.

Extends operational_history trend with windowed aggregates for dashboards.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def window_points(history: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    if not history:
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    result = []
    for item in history:
        dt = parse_dt(item.get("snapshot_at_utc"))
        if dt and dt.timestamp() >= cutoff:
            result.append(item)
    return result if result else history[-min(len(history), 10) :]


def aggregate_window(points: list[dict[str, Any]]) -> dict[str, Any]:
    if not points:
        return {"points": 0}
    scores = [float(p.get("hub_score") or 0) for p in points]
    failures = [float((p.get("metrics") or {}).get("overall_failure_rate_percent") or 0) for p in points]
    mttrs = [
        float((p.get("metrics") or {}).get("mttr_minutes"))
        for p in points
        if (p.get("metrics") or {}).get("mttr_minutes") is not None
    ]
    return {
        "points": len(points),
        "avg_hub_score": round(sum(scores) / len(scores), 2),
        "min_hub_score": round(min(scores), 2),
        "max_hub_score": round(max(scores), 2),
        "avg_failure_rate_percent": round(sum(failures) / len(failures), 2),
        "avg_mttr_minutes": round(sum(mttrs) / len(mttrs), 2) if mttrs else None,
        "trend_direction": (
            "melhorando"
            if scores[-1] - scores[0] > 2
            else "piorando"
            if scores[-1] - scores[0] < -2
            else "estavel"
        ),
    }


def build_report(history: list[dict[str, Any]], trend: dict[str, Any], commit_sha: str) -> dict[str, Any]:
    windows = {
        "7d": aggregate_window(window_points(history, 7)),
        "30d": aggregate_window(window_points(history, 30)),
    }
    latest = history[-1] if history else {}
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "operational-longitudinal-analytics",
        "status": trend.get("direction", "unknown"),
        "confidence_level": "high" if len(history) >= 3 else "medium" if history else "low",
        "maturity_percent": round(float(latest.get("hub_score") or trend.get("last_score") or 0), 2),
        "operational_risk": "high" if trend.get("direction") == "piorando" else "low",
        "commit_sha": commit_sha,
        "correlation_id": str(uuid4()),
        "mode": "report_only",
        "history_points_total": len(history),
        "trend": trend,
        "windows": windows,
        "latest_snapshot_at": latest.get("snapshot_at_utc"),
        "metrics": latest.get("metrics") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build longitudinal operational analytics.")
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("artifacts/operational-history/operational-history.json"),
    )
    parser.add_argument(
        "--trend",
        type=Path,
        default=Path("artifacts/operational-history/operational-history-trend.json"),
    )
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-longitudinal-analytics"))
    args = parser.parse_args()

    history = load_json(args.history, [])
    if not isinstance(history, list):
        history = []
    trend = load_json(args.trend, {"direction": "unknown", "points": 0})
    report = build_report(history, trend, args.commit_sha)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "longitudinal-analytics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"points={report['history_points_total']} trend={report['trend'].get('direction')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
