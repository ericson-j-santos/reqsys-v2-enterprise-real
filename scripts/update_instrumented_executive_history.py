#!/usr/bin/env python3
"""Persist instrumented executive snapshots and derive evidence-based ETA."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGETS = {"mvp": 90.0, "production": 95.0, "gold_standard": 95.0}


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def metric(snapshot: dict[str, Any], milestone: str) -> float | None:
    indicators = snapshot.get("indicators") or {}
    mapping = {
        "mvp": indicators.get("technical_progress_percent"),
        "production": indicators.get("production_percent"),
        "gold_standard": snapshot.get("operational_readiness_percent"),
    }
    value = mapping[milestone]
    return None if value is None else float(value)


def derive_eta(points: list[dict[str, Any]], milestone: str) -> dict[str, Any]:
    usable = [(parse_time(point["generated_at"]), metric(point, milestone)) for point in points]
    usable = [(when, value) for when, value in usable if value is not None]
    current = usable[-1][1] if usable else None
    target = TARGETS[milestone]
    if current is None:
        return {"status": "insufficient_evidence", "target_percent": target, "current_percent": None, "eta_days": None}
    if current >= target:
        return {"status": "achieved", "target_percent": target, "current_percent": round(current, 2), "eta_days": 0.0}
    if len(usable) < 2:
        return {"status": "insufficient_history", "target_percent": target, "current_percent": round(current, 2), "eta_days": None}
    first_time, first_value = usable[0]
    last_time, last_value = usable[-1]
    elapsed_days = max((last_time - first_time).total_seconds() / 86400, 0)
    velocity = None if elapsed_days == 0 else (last_value - first_value) / elapsed_days
    if velocity is None or velocity <= 0:
        return {"status": "no_positive_velocity", "target_percent": target, "current_percent": round(current, 2), "velocity_percent_per_day": None if velocity is None else round(velocity, 4), "eta_days": None}
    eta = (target - current) / velocity
    return {"status": "projected", "target_percent": target, "current_percent": round(current, 2), "velocity_percent_per_day": round(velocity, 4), "eta_days": round(max(0, eta), 2)}


def update_history(history: dict[str, Any], snapshot: dict[str, Any], max_points: int = 180) -> dict[str, Any]:
    points = list(history.get("points") or [])
    identity = (snapshot.get("generated_at"), snapshot.get("contract"))
    if identity not in {(point.get("generated_at"), point.get("contract")) for point in points}:
        points.append(snapshot)
    points.sort(key=lambda point: point.get("generated_at") or "")
    points = points[-max_points:]
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-instrumented-executive-history",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report_only",
        "production_blocker": False,
        "automatic_promotion_allowed": False,
        "snapshot_count": len(points),
        "metric_coverage_percent": snapshot.get("metric_coverage_percent"),
        "eta": {name: derive_eta(points, name) for name in TARGETS},
        "points": points,
        "source_contract": snapshot.get("contract"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-points", type=int, default=180)
    args = parser.parse_args()
    result = update_history(load_object(args.history), load_object(args.snapshot), args.max_points)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"snapshots": result["snapshot_count"], "eta": result["eta"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
