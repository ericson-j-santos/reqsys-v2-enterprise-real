#!/usr/bin/env python3
"""Valida o card de tendência de homologação no artifact canônico do Ops Dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_homologation_trend"
REQUIRED_TOKENS = {
    'id="executive-promotion-advisor-homologation-trend-card"',
    'id="advisor-trend-samples"',
    'id="advisor-trend-rate"',
    'id="advisor-trend-streak"',
    'id="advisor-trend-eligibility"',
    "function renderExecutivePromotionAdvisorHomologationTrend(payload)",
    "renderExecutivePromotionAdvisorHomologationTrend(payload);",
    "payload?.cards?.executive_promotion_advisor_homologation_trend",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON deve ser objeto: {path}")
    return payload


def validate(dashboard: Path, runtime_index: Path) -> dict[str, Any]:
    html = dashboard.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_TOKENS if token not in html)
    if missing:
        raise ValueError(f"tokens ausentes: {missing}")
    if html.count('id="executive-promotion-advisor-homologation-trend-card"') != 1:
        raise ValueError("card de tendência deve existir exatamente uma vez")
    if html.count("function renderExecutivePromotionAdvisorHomologationTrend(payload)") != 1:
        raise ValueError("função de tendência deve existir exatamente uma vez")
    if "fetch('http" in html or 'fetch("http' in html:
        raise ValueError("card não pode introduzir chamadas externas")

    runtime = load_json(runtime_index)
    card = (runtime.get("cards") or {}).get(CARD_KEY)
    if not isinstance(card, dict):
        raise ValueError("contrato de tendência ausente")
    if card.get("mode") != "report-only":
        raise ValueError("mode deve ser report-only")
    if card.get("production_blocker") is not False:
        raise ValueError("production_blocker deve ser false")
    if card.get("human_approval_required") is not True:
        raise ValueError("human_approval_required deve ser true")
    if not isinstance(card.get("eligible_for_gate_review"), bool):
        raise ValueError("eligible_for_gate_review deve ser booleano")

    return {
        "status": "passed",
        "card": CARD_KEY,
        "sample_count": int(card.get("sample_count") or 0),
        "trend": card.get("trend") or "insufficient-data",
        "eligible_for_gate_review": card["eligible_for_gate_review"],
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        evidence = validate(args.dashboard, args.runtime_index)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
