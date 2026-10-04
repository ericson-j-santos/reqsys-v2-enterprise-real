#!/usr/bin/env python3
"""Valida o card e o contrato canônico do índice executivo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CARD_ID = "executive-sync-stability-index-card"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    if html.count(f'id="{CARD_ID}"') != 1:
        raise SystemExit("card ausente ou duplicado")
    lowered = html.lower()
    for forbidden in ("fetch(", "xmlhttprequest", "axios.", "http://", "https://"):
        if forbidden in lowered:
            raise SystemExit(f"chamada externa proibida: {forbidden}")

    data = json.loads(args.runtime_index.read_text(encoding="utf-8"))
    card = (data.get("cards") or {}).get("executive_sync_stability_index")
    if not isinstance(card, dict):
        raise SystemExit("contrato executive_sync_stability_index ausente")
    if card.get("mode") != "report-only":
        raise SystemExit("mode deve ser report-only")
    if card.get("production_blocker") is not False:
        raise SystemExit("production_blocker deve ser false")
    if card.get("human_approval_required") is not True:
        raise SystemExit("human_approval_required deve ser true")

    print("EXECUTIVE_SYNC_STABILITY_INDEX_CARD_VALID")


if __name__ == "__main__":
    main()
