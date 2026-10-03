#!/usr/bin/env python3
"""Publica de forma idempotente o indicador de confiabilidade do Dashboard UX."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-confidence-dashboard-reliability"


def _safe_indicator(indicator: dict[str, Any] | None) -> dict[str, Any]:
    source = deepcopy(indicator or {})
    status = source.get("status", "UX_CONFIDENCE_CARD_AVAILABILITY_REVIEW")
    stable = status == "UX_CONFIDENCE_CARD_AVAILABILITY_STABLE"
    return {
        "id": CARD_ID,
        "title": "Confiabilidade do Dashboard UX",
        "status": status,
        "availability_rate": float(source.get("availability_rate", 0.0)),
        "stable_sequence": int(source.get("stable_sequence", 0)),
        "sample_count": int(source.get("sample_count", 0)),
        "confidence_score": int(source.get("confidence_score", 0)),
        "common_fingerprint": source.get("common_fingerprint"),
        "recurring_drift": bool(source.get("recurring_drift", True)),
        "human_review_eligible": bool(source.get("human_review_eligible", False) and stable),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def inject_card(dashboard: dict[str, Any], indicator: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(dashboard)
    cards = [card for card in result.get("cards", []) if card.get("id") != CARD_ID]
    cards.append(_safe_indicator(indicator))
    result["cards"] = cards
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--indicator", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    indicator_payload = json.loads(Path(args.indicator).read_text(encoding="utf-8"))
    indicator = indicator_payload.get("indicators", {}).get(
        "user_experience_sync_confidence_availability",
        indicator_payload,
    )
    output = inject_card(dashboard, indicator)
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
