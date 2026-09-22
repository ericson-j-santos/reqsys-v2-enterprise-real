#!/usr/bin/env python3
"""Valida sincronização e guardrails do indicador de jornada do usuário."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

KEY = "user_experience_journey_quality"
CARD_ID = "user-experience-journey-quality"


def validate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    state_indicator = state.get("cards", {}).get(KEY)
    brief_indicator = brief.get("indicators", {}).get(KEY)
    cards = [item for item in dashboard.get("cards", []) if isinstance(item, dict) and item.get("id") == CARD_ID]
    dashboard_indicator = cards[0] if len(cards) == 1 else None

    if len(cards) != 1:
        errors.append(f"dashboard deve conter exatamente um card {CARD_ID}")
    if not isinstance(state_indicator, dict) or not isinstance(brief_indicator, dict) or not isinstance(dashboard_indicator, dict):
        errors.append("indicador ausente em uma ou mais fontes")
        return errors
    if state_indicator != brief_indicator or state_indicator != dashboard_indicator:
        errors.append("drift entre Estado Único, Executive Brief e Ops Dashboard")
    if state_indicator.get("mode") != "report-only":
        errors.append("mode deve permanecer report-only")
    if state_indicator.get("production_blocker") is not False:
        errors.append("production_blocker deve permanecer false")
    if state_indicator.get("human_approval_required") is not True:
        errors.append("human_approval_required deve permanecer true")
    if state_indicator.get("quality_score", 0) < 0 or state_indicator.get("quality_score", 0) > 100:
        errors.append("quality_score fora do intervalo 0..100")
    return errors


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    args = parser.parse_args()
    errors = validate(_read(args.state), _read(args.brief), _read(args.dashboard))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("UX_JOURNEY_QUALITY_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
