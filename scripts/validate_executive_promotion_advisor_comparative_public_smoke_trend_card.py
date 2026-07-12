#!/usr/bin/env python3
"""Validate the canonical comparative public smoke trend card."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CARD_KEY = "executive_promotion_advisor_comparative_public_smoke_trend"
HOOK = "<!-- REQSYS_EXECUTIVE_PROMOTION_ADVISOR_COMPARATIVE_SMOKE_TREND -->"


def validate(html: str, runtime_index: dict) -> None:
    if html.count(HOOK) != 1:
        raise ValueError("comparative smoke trend hook must exist exactly once")
    if "http://" in html or "https://" in html:
        raise ValueError("external calls are not allowed in the injected card")
    card = runtime_index.get("cards", {}).get(CARD_KEY)
    if not isinstance(card, dict):
        raise ValueError("canonical trend card is missing")
    if card.get("mode") != "report-only":
        raise ValueError("mode must be report-only")
    if card.get("production_blocker") is not False:
        raise ValueError("production_blocker must be false")
    if card.get("human_approval_required") is not True:
        raise ValueError("human approval must remain mandatory")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--runtime-index", required=True)
    args = parser.parse_args()
    validate(
        Path(args.html).read_text(encoding="utf-8"),
        json.loads(Path(args.runtime_index).read_text(encoding="utf-8")),
    )
    print("ADVISOR_COMPARATIVE_SMOKE_TREND_CARD_VALID")


if __name__ == "__main__":
    main()
