#!/usr/bin/env python3
"""Publica o indicador UX evidenciado no Ops Dashboard canônico.

A publicação é informativa e preserva decisão humana, readiness e deploy.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-evidence"
SOURCE_KEY = "user_experience_evidence"


def build_card(source: dict[str, Any] | None) -> dict[str, Any]:
    source = source or {}
    score = int(source.get("score", source.get("value", 0)) or 0)
    evidenced = bool(source.get("evidenced", False))
    consolidated = bool(source.get("consolidated", False))
    return {
        "id": CARD_ID,
        "title": "Experiência do usuário final",
        "score": score,
        "status": source.get("status", "collecting-evidence"),
        "evidenced": evidenced,
        "consolidated": consolidated,
        "scenarios": list(source.get("scenarios", [])),
        "workflow_run_id": source.get("workflow_run_id"),
        "artifact": deepcopy(source.get("artifact", {})),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def publish(index: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(dashboard)
    cards = result.setdefault("cards", [])
    cards[:] = [card for card in cards if card.get("id") != CARD_ID]
    source = index.get("cards", {}).get(SOURCE_KEY)
    cards.append(build_card(source))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    output = publish(index, dashboard)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
