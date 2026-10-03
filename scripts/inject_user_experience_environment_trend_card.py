#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-environment-trend"
SOURCE_KEY = "user_experience_environment_trend"


def inject(index: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    source = index.get("cards", {}).get(SOURCE_KEY) or {}
    card = {
        "id": CARD_ID,
        "title": "Tendência histórica UX ambiental",
        "status": source.get("status", "UX_ENV_TREND_REVIEW"),
        "sample_count": int(source.get("sample_count", 0)),
        "success_rate": float(source.get("success_rate", 0)),
        "stable_sequence": int(source.get("stable_sequence", 0)),
        "recurring_drift": bool(source.get("recurring_drift", False)),
        "degradation_detected": bool(source.get("degradation_detected", False)),
        "eligible_for_human_review": bool(source.get("eligible_for_human_review", False)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    cards = dashboard.setdefault("cards", [])
    cards[:] = [item for item in cards if item.get("id") != CARD_ID]
    cards.append(card)
    return dashboard


def validate(dashboard: dict[str, Any]) -> list[str]:
    cards = [c for c in dashboard.get("cards", []) if c.get("id") == CARD_ID]
    if len(cards) != 1: return [f"expected one {CARD_ID} card"]
    card = cards[0]; errors: list[str] = []
    if card.get("mode") != "report-only": errors.append("mode must be report-only")
    if card.get("production_blocker") is not False: errors.append("production_blocker must be false")
    if card.get("human_approval_required") is not True: errors.append("human approval required")
    if card.get("eligible_for_human_review"):
        if card.get("status") != "UX_ENV_TREND_STABLE": errors.append("eligible status must be stable")
        if int(card.get("sample_count", 0)) < 3: errors.append("eligible requires 3 samples")
        if float(card.get("success_rate", 0)) < 100: errors.append("eligible requires 100%")
        if int(card.get("stable_sequence", 0)) < 3: errors.append("eligible requires stable sequence")
        if card.get("recurring_drift") or card.get("degradation_detected"): errors.append("eligible cannot have drift/degradation")
    return errors


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--index", required=True); p.add_argument("--dashboard", required=True); p.add_argument("--output", required=True)
    a=p.parse_args(); result=inject(json.loads(Path(a.index).read_text()), json.loads(Path(a.dashboard).read_text()))
    errors=validate(result)
    if errors: raise SystemExit("\n".join(errors))
    Path(a.output).write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
