#!/usr/bin/env python3
"""Publica o indicador de confiabilidade contínua do Dashboard no Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

CARD_ID = "user-experience-dashboard-continuous-reliability"


def _safe_indicator(indicator: Dict[str, Any] | None) -> Dict[str, Any]:
    source = indicator if isinstance(indicator, dict) else {}
    return {
        "id": CARD_ID,
        "title": "Confiabilidade contínua do Dashboard UX",
        "status": source.get("status", "UX_DASHBOARD_CONTINUOUS_RELIABILITY_REVIEW"),
        "success_rate": float(source.get("success_rate", 0.0)),
        "stable_streak": int(source.get("stable_streak", 0)),
        "samples": int(source.get("samples", 0)),
        "confidence_score": int(source.get("confidence_score", 0)),
        "common_fingerprint": source.get("common_fingerprint"),
        "recurrent_drift": bool(source.get("recurrent_drift", True)),
        "human_review_eligible": bool(source.get("human_review_eligible", False)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def inject_card(dashboard: Dict[str, Any], indicator: Dict[str, Any] | None) -> Dict[str, Any]:
    result = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = result.setdefault("cards", [])
    if not isinstance(cards, list):
        cards = []
        result["cards"] = cards
    card = _safe_indicator(indicator)
    remaining = [item for item in cards if not (isinstance(item, dict) and item.get("id") == CARD_ID)]
    remaining.append(card)
    result["cards"] = remaining
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--indicator", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    indicator_doc = json.loads(Path(args.indicator).read_text(encoding="utf-8"))
    indicator = indicator_doc.get("indicators", {}).get("user_experience_dashboard_continuous_reliability")
    output = inject_card(dashboard, indicator)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
