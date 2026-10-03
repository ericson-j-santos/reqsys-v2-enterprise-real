#!/usr/bin/env python3
"""Valida o card do histórico final sincronizado no Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.inject_executive_final_sync_history_state_card import CARD_ID, CARD_KEY


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
    if card.get("eligible_for_human_review"):
        if not card.get("coverage_complete"):
            errors.append("eligibility requires complete environment coverage")
        if not card.get("synchronized"):
            errors.append("eligibility requires synchronized environments")
        if int(card.get("minimum_stable_sequence", 0) or 0) < 3:
            errors.append("eligibility requires minimum stable sequence of 3")
        if float(card.get("weighted_pass_rate_percent", 0.0) or 0.0) != 100.0:
            errors.append("eligibility requires 100 percent pass rate")
        if not str(card.get("common_fingerprint", "")):
            errors.append("eligibility requires common fingerprint")
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
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
