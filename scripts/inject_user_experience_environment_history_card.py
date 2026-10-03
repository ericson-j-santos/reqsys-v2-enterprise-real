#!/usr/bin/env python3
"""Publish the consolidated UX environment history in the Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-environment-history"
SOURCE_KEY = "user_experience_environment_history"


def build_card(source: dict[str, Any] | None) -> dict[str, Any]:
    source = source or {}
    return {
        "id": CARD_ID,
        "title": "Histórico ambiental da experiência do usuário",
        "status": source.get("status", "collecting-evidence"),
        "environment_coverage": source.get("environment_coverage", []),
        "pass_rate_by_environment": source.get("pass_rate_by_environment", {}),
        "minimum_pass_rate": source.get("minimum_pass_rate", 0),
        "stable_sequence": source.get("stable_sequence", 0),
        "common_fingerprint": source.get("common_fingerprint"),
        "drift_detected": bool(source.get("drift_detected", True)),
        "eligible_for_human_review": bool(source.get("eligible_for_human_review", False)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def inject(index: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    cards = dashboard.setdefault("cards", [])
    cards[:] = [card for card in cards if card.get("id") != CARD_ID]
    source = index.get("cards", {}).get(SOURCE_KEY)
    cards.append(build_card(source))
    return dashboard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    result = inject(index, dashboard)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
