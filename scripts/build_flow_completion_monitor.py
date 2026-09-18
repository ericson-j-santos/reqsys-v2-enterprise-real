#!/usr/bin/env python3
"""Consolida execuções de fluxo por ambiente e mantém abertas as incompletas."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL_SUCCESS = "succeeded"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_monitor(definition: dict[str, Any], executions: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    environments = sorted(definition["environments"], key=lambda item: item["order"])
    required_positions = [
        (environment["name"], stage["name"])
        for environment in environments if environment.get("required", True)
        for stage in sorted(environment["stages"], key=lambda item: item["order"])
        if stage.get("required", True)
    ]
    final_environment, final_stage = required_positions[-1]

    items: list[dict[str, Any]] = []
    for execution in executions:
        latest = {
            (event["environment"], event["stage"]): event
            for event in sorted(execution.get("events", []), key=lambda item: item.get("updated_at", ""))
        }
        final_event = latest.get((final_environment, final_stage))
        completed = bool(
            final_event
            and final_event.get("status") == TERMINAL_SUCCESS
            and final_event.get("evidence_url")
            and final_event.get("commit_sha") == execution.get("expected_commit_sha")
        )

        last_position = None
        for position in required_positions:
            event = latest.get(position)
            if event and event.get("status") == TERMINAL_SUCCESS:
                last_position = position
            else:
                break

        next_position = None
        if not completed:
            completed_count = 0 if last_position is None else required_positions.index(last_position) + 1
            if completed_count < len(required_positions):
                next_position = required_positions[completed_count]

        last_activity = max((parse_time(item.get("updated_at")) for item in latest.values()), default=None)
        age_hours = round((now - last_activity).total_seconds() / 3600, 2) if last_activity else None
        statuses = {item.get("status") for item in latest.values()}
        if completed:
            status = "COMPLETED"
        elif "failed" in statuses:
            status = "FAILED"
        elif "blocked" in statuses:
            status = "BLOCKED"
        elif last_activity and age_hours is not None and age_hours >= definition.get("stale_after_hours", 24):
            status = "STALE"
        else:
            status = "IN_PROGRESS" if latest else "PENDING"

        items.append({
            "execution_id": execution["execution_id"],
            "item_id": execution["item_id"],
            "expected_commit_sha": execution.get("expected_commit_sha"),
            "status": status,
            "completed": completed,
            "last_completed": ({"environment": last_position[0], "stage": last_position[1]} if last_position else None),
            "next_expected": ({"environment": next_position[0], "stage": next_position[1]} if next_position else None),
            "age_hours": age_hours,
            "final_environment": final_environment,
            "final_stage": final_stage,
            "evidence_url": final_event.get("evidence_url") if final_event else None,
        })

    open_items = [item for item in items if not item["completed"]]
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-flow-completion-monitor",
        "generated_at": now.isoformat(),
        "flow": definition["flow"],
        "final_environment": final_environment,
        "final_stage": final_stage,
        "summary": {
            "total": len(items),
            "open": len(open_items),
            "completed": len(items) - len(open_items),
            "blocked": sum(item["status"] == "BLOCKED" for item in items),
            "failed": sum(item["status"] == "FAILED" for item in items),
            "stale": sum(item["status"] == "STALE" for item in items),
        },
        "open_items": open_items,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--definition", required=True, type=Path)
    parser.add_argument("--executions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_monitor(load_json(args.definition), load_json(args.executions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
