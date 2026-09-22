#!/usr/bin/env python3
"""Publica, de forma idempotente, o card de estabilidade executiva UX no Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

CARD_ID = "user-experience-dashboard-executive-stability"


def _fallback() -> Dict[str, Any]:
    return {
        "id": CARD_ID,
        "status": "UX_DASHBOARD_EXECUTIVE_STABILITY_REVIEW",
        "success_rate": 0.0,
        "stable_sequence": 0,
        "sample_count": 0,
        "confidence_score": 0,
        "common_fingerprint": None,
        "recurring_drift": False,
        "human_review_eligible": False,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def build_card(state: Dict[str, Any]) -> Dict[str, Any]:
    source = state.get("cards", {}).get("user_experience_dashboard_executive_stability")
    card = _fallback()
    if isinstance(source, dict):
        for key in (
            "status", "success_rate", "stable_sequence", "sample_count",
            "confidence_score", "common_fingerprint", "recurring_drift",
            "human_review_eligible", "mode", "production_blocker",
            "human_approval_required",
        ):
            if key in source:
                card[key] = source[key]
    card["mode"] = "report-only"
    card["production_blocker"] = False
    card["human_approval_required"] = True
    return card


def inject_card(dashboard: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(dashboard)
    cards = result.setdefault("cards", [])
    card = build_card(state)
    result["cards"] = [item for item in cards if item.get("id") != CARD_ID] + [card]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    Path(args.output).write_text(json.dumps(inject_card(dashboard, state), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
