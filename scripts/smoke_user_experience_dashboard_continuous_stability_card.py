#!/usr/bin/env python3
"""Valida o card de estabilidade contínua entre Estado Único, Executive Brief e Dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-dashboard-continuous-stability"
KEY = "user_experience_dashboard_continuous_stability"
FIELDS = (
    "status", "success_rate", "stable_sequence", "sample_count",
    "confidence_score", "common_fingerprint", "recurring_drift",
    "human_review_eligible", "mode", "production_blocker",
    "human_approval_required",
)


def _canonical(value: dict[str, Any] | None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {field: source.get(field) for field in FIELDS}


def evaluate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state_value = state.get("cards", {}).get(KEY)
    brief_value = brief.get("indicators", {}).get(KEY)
    matches = [item for item in dashboard.get("cards", []) if isinstance(item, dict) and item.get("id") == CARD_ID]
    dashboard_value = matches[0] if len(matches) == 1 else None
    values = [_canonical(state_value), _canonical(brief_value), _canonical(dashboard_value)]
    synchronized = values[0] == values[1] == values[2]
    guardrails_ok = all(
        item.get("mode") == "report-only"
        and item.get("production_blocker") is False
        and item.get("human_approval_required") is True
        for item in values
    )
    fingerprint = hashlib.sha256(json.dumps(values[0], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    ok = synchronized and guardrails_ok and len(matches) == 1
    return {
        "status": "UX_DASHBOARD_CONTINUOUS_STABILITY_CARD_OK" if ok else "UX_DASHBOARD_CONTINUOUS_STABILITY_CARD_REVIEW",
        "synchronized": synchronized,
        "guardrails_ok": guardrails_ok,
        "card_count": len(matches),
        "fingerprint": fingerprint,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = evaluate(load(args.state), load(args.brief), load(args.dashboard))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"].endswith("_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
