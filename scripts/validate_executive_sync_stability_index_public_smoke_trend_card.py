#!/usr/bin/env python3
"""Valida o card público de tendência do índice executivo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.inject_executive_sync_stability_index_public_smoke_trend_card import CARD_ID, CARD_KEY


def validate(html_text: str, runtime_index: dict) -> list[str]:
    errors: list[str] = []
    card = runtime_index.get("cards", {}).get(CARD_KEY)
    if not isinstance(card, dict):
        return ["missing runtime card contract"]
    if html_text.count(f'id="{CARD_ID}"') != 1:
        errors.append("card must be present exactly once")
    if card.get("mode") != "report-only":
        errors.append("mode must be report-only")
    if card.get("production_blocker") is not False:
        errors.append("production_blocker must be false")
    if card.get("human_approval_required") is not True:
        errors.append("human_approval_required must be true")
    if card.get("eligible_for_human_review") and not card.get("coverage_complete"):
        errors.append("eligibility requires complete environment coverage")
    if card.get("eligible_for_human_review") and not card.get("synchronized"):
        errors.append("eligibility requires synchronized environments")
    lowered = html_text.lower()
    for forbidden in ("fetch(", "xmlhttprequest", "axios."):
        if forbidden in lowered:
            errors.append(f"external browser call forbidden: {forbidden}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    runtime = json.loads(args.runtime_index.read_text(encoding="utf-8"))
    errors = validate(args.html.read_text(encoding="utf-8"), runtime)
    evidence = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
