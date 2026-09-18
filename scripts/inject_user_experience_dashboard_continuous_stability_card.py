#!/usr/bin/env python3
"""Publica o indicador de estabilidade contínua do Dashboard UX no Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-dashboard-continuous-stability"
KEY = "user_experience_dashboard_continuous_stability"


def _safe(value: dict[str, Any] | None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "id": CARD_ID,
        "title": "Estabilidade contínua do Dashboard UX",
        "status": source.get("status", "UX_DASHBOARD_CONTINUOUS_STABILITY_REVIEW"),
        "success_rate": float(source.get("success_rate", 0.0) or 0.0),
        "stable_sequence": int(source.get("stable_sequence", 0) or 0),
        "sample_count": int(source.get("sample_count", source.get("samples", 0)) or 0),
        "confidence_score": int(source.get("confidence_score", 0) or 0),
        "common_fingerprint": source.get("common_fingerprint"),
        "recurring_drift": bool(source.get("recurring_drift", source.get("recurrent_drift", True))),
        "human_review_eligible": bool(source.get("human_review_eligible", source.get("eligible_for_human_review", False))),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def inject(dashboard: dict[str, Any], indicator: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    cards = result.get("cards", [])
    if not isinstance(cards, list):
        cards = []
    result["cards"] = [item for item in cards if not (isinstance(item, dict) and item.get("id") == CARD_ID)]
    result["cards"].append(_safe(indicator))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--indicator", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    payload = json.loads(args.indicator.read_text(encoding="utf-8"))
    indicator = payload.get("indicators", {}).get(KEY, payload.get("cards", {}).get(KEY, payload))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inject(dashboard, indicator), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
