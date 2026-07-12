#!/usr/bin/env python3
"""Validate the canonical Executive Sync Stability Index dashboard card."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CARD_ID = "executive-sync-stability-index"


def validate(html_text: str, runtime_index: dict) -> list[str]:
    errors: list[str] = []
    card = runtime_index.get("cards", {}).get("executive_sync_stability_index")
    if not isinstance(card, dict):
        errors.append("missing runtime card contract")
        return errors
    if html_text.count(f'id="{CARD_ID}"') != 1:
        errors.append("card must be present exactly once")
    if card.get("mode") != "report-only":
        errors.append("mode must be report-only")
    if card.get("production_blocker") is not False:
        errors.append("production_blocker must be false")
    if card.get("human_approval_required") is not True:
        errors.append("human_approval_required must be true")
    lowered = html_text.lower()
    for forbidden in ("fetch(", "xmlhttprequest", "axios."):
        if forbidden in lowered:
            errors.append(f"external browser call forbidden: {forbidden}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--runtime-index", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()

    html_text = Path(args.html).read_text(encoding="utf-8")
    runtime = json.loads(Path(args.runtime_index).read_text(encoding="utf-8"))
    errors = validate(html_text, runtime)
    evidence = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    Path(args.evidence).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
