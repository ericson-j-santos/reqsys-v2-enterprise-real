#!/usr/bin/env python3
"""Valida o card comparativo DEV/STG/PROD do Advisor no Ops Dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_public_smoke_comparative"
REQUIRED_TOKENS = {
    'id="executive-promotion-advisor-public-smoke-comparative-card"',
    'id="advisor-public-comparative-coverage"',
    'id="advisor-public-comparative-rate"',
    'id="advisor-public-comparative-min-rate"',
    'id="advisor-public-comparative-trend"',
    "function renderExecutivePromotionAdvisorPublicSmokeComparative(payload)",
    "renderExecutivePromotionAdvisorPublicSmokeComparative(payload);",
    "payload?.cards?.executive_promotion_advisor_public_smoke_comparative",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contrato JSON deve ser objeto")
    return payload


def validate(dashboard: Path, runtime_index: Path) -> dict[str, Any]:
    html = dashboard.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_TOKENS if token not in html)
    if missing:
        raise ValueError(f"tokens ausentes: {missing}")
    if html.count('id="executive-promotion-advisor-public-smoke-comparative-card"') != 1:
        raise ValueError("card comparativo deve existir exatamente uma vez")
    if html.count("function renderExecutivePromotionAdvisorPublicSmokeComparative(payload)") != 1:
        raise ValueError("função comparativa deve existir exatamente uma vez")
    if "fetch('http" in html or 'fetch("http' in html:
        raise ValueError("card comparativo não pode introduzir chamadas externas")

    runtime = load_json(runtime_index)
    card = (runtime.get("cards") or {}).get(CARD_KEY)
    if not isinstance(card, dict):
        raise ValueError("card comparativo ausente do Runtime Executive Index")
    if card.get("mode") != "report-only":
        raise ValueError("mode deve ser report-only")
    if card.get("production_blocker") is not False:
        raise ValueError("production_blocker deve ser false")
    if card.get("human_approval_required") is not True:
        raise ValueError("human_approval_required deve ser true")
    if not isinstance(card.get("eligible_for_human_review"), bool):
        raise ValueError("eligible_for_human_review deve ser booleano")
    if not isinstance(card.get("complete_environment_coverage"), bool):
        raise ValueError("complete_environment_coverage deve ser booleano")

    return {
        "status": "passed",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "environment_count": int(card.get("environment_count") or 0),
        "trend": card.get("trend") or "insufficient-environment-coverage",
        "eligible_for_human_review": bool(card.get("eligible_for_human_review")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida comparativo público do Advisor no dashboard")
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = validate(args.dashboard, args.runtime_index)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
