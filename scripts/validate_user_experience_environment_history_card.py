#!/usr/bin/env python3
"""Validate the UX environment-history card contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-environment-history"


def validate(dashboard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cards = [card for card in dashboard.get("cards", []) if card.get("id") == CARD_ID]
    if len(cards) != 1:
        return [f"expected exactly one {CARD_ID} card, found {len(cards)}"]

    card = cards[0]
    if card.get("mode") != "report-only":
        errors.append("mode must be report-only")
    if card.get("production_blocker") is not False:
        errors.append("production_blocker must be false")
    if card.get("human_approval_required") is not True:
        errors.append("human approval must remain required")

    if card.get("eligible_for_human_review"):
        if set(card.get("environment_coverage") or []) != {"DEV", "STG", "PROD"}:
            errors.append("eligible card requires DEV/STG/PROD coverage")
        if float(card.get("minimum_pass_rate", 0)) < 100:
            errors.append("eligible card requires 100% minimum pass rate")
        if int(card.get("stable_sequence", 0)) < 3:
            errors.append("eligible card requires stable sequence >= 3")
        if card.get("drift_detected") is not False:
            errors.append("eligible card cannot contain drift")
        if not card.get("common_fingerprint"):
            errors.append("eligible card requires a common fingerprint")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    args = parser.parse_args()
    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    errors = validate(dashboard)
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
