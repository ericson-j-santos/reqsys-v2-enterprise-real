#!/usr/bin/env python3
"""Publica de forma idempotente o card de confiança da sincronização UX."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-sync-confidence"


def _safe_indicator(indicator: dict[str, Any] | None) -> dict[str, Any]:
    indicator = indicator or {}
    return {
        "id": CARD_ID,
        "title": "Confiança operacional da sincronização UX",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "status": indicator.get("status", "UX_SYNC_CONFIDENCE_REVIEW"),
        "confidence_level": indicator.get("confidence_level", "LOW"),
        "confidence_score": int(indicator.get("confidence_score", 0) or 0),
        "sample_count": int(indicator.get("sample_count", 0) or 0),
        "sync_rate": float(indicator.get("sync_rate", 0.0) or 0.0),
        "stable_sequence": int(indicator.get("stable_sequence", 0) or 0),
        "recurrent_drift": bool(indicator.get("recurrent_drift", True)),
        "human_review_eligible": bool(indicator.get("human_review_eligible", False)),
    }


def inject(dashboard: dict[str, Any], executive_brief: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(dashboard))
    cards = result.setdefault("cards", [])
    indicator = executive_brief.get("indicators", {}).get("user_experience_sync_confidence")
    card = _safe_indicator(indicator)
    cards[:] = [item for item in cards if item.get("id") != CARD_ID]
    cards.append(card)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--executive-brief", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    executive = json.loads(Path(args.executive_brief).read_text(encoding="utf-8"))
    output = inject(dashboard, executive)
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
