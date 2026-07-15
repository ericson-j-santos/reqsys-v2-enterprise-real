#!/usr/bin/env python3
"""Consolida telemetria segura de estados vazios no Estado Único ReqSys."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

KEY = "user_experience_empty_states"
CARD_ID = "user-experience-empty-states"


def evaluate(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    items = [e for e in (events or []) if isinstance(e, dict)]
    views = sum(1 for e in items if e.get("event") == "view")
    primary = sum(1 for e in items if e.get("event") == "primary_action")
    secondary = sum(1 for e in items if e.get("event") == "secondary_action")
    recoveries = primary + secondary
    recovery_rate = round((recoveries / views) * 100, 1) if views else 0.0
    contexts = Counter(str(e.get("context", "unknown"))[:80] for e in items)
    status = "UX_EMPTY_STATES_STABLE" if views >= 3 and recovery_rate >= 30 else "UX_EMPTY_STATES_REVIEW"
    return {
        "id": CARD_ID,
        "title": "Estados vazios orientativos",
        "status": status,
        "views": views,
        "primary_actions": primary,
        "secondary_actions": secondary,
        "recovery_rate": recovery_rate,
        "contexts": dict(contexts.most_common(10)),
        "sample_count": len(items),
        "evidence_complete": views > 0,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def consolidate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any], indicator: dict[str, Any]):
    state_out, brief_out, dashboard_out = deepcopy(state), deepcopy(brief), deepcopy(dashboard)
    state_out.setdefault("indicators", {})[KEY] = indicator
    brief_out.setdefault("indicators", {})[KEY] = indicator
    cards = dashboard_out.get("cards", [])
    cards = cards if isinstance(cards, list) else []
    dashboard_out["cards"] = [c for c in cards if not (isinstance(c, dict) and c.get("id") == CARD_ID)] + [indicator]
    return state_out, brief_out, dashboard_out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.telemetry.read_text(encoding="utf-8"))
    events = payload if isinstance(payload, list) else payload.get("events", [])
    indicator = evaluate(events)
    outputs = consolidate(
        json.loads(args.state.read_text(encoding="utf-8")),
        json.loads(args.brief.read_text(encoding="utf-8")),
        json.loads(args.dashboard.read_text(encoding="utf-8")),
        indicator,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in zip(("estado-unico.json", "executive-brief.json", "ops-dashboard.json"), outputs):
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "empty-state-indicator.json").write_text(json.dumps(indicator, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
