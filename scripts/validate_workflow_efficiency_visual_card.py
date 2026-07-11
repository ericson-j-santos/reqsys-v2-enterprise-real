#!/usr/bin/env python3
"""Valida Workflow Efficiency e Executive Promotion Advisor no Ops Dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.validate_executive_promotion_advisor_card import validate as validate_advisor

REQUIRED_TOKENS = {
    'id="workflow-efficiency-visual-card"',
    'id="workflow-efficiency-score"',
    'id="workflow-efficiency-trend"',
    'id="workflow-efficiency-savings"',
    'id="workflow-efficiency-action"',
    'function renderWorkflowEfficiency(payload)',
    'renderWorkflowEfficiency(payload);',
    'payload?.cards?.workflow_efficiency',
    'payload?.links?.workflow_efficiency',
    'runtime-executive-index.json',
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida cards Workflow Efficiency e Promotion Advisor")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    parser.add_argument("--runtime-index", type=Path, default=Path("docs/ops-dashboard/data/runtime-executive-index.json"))
    args = parser.parse_args()

    if not args.dashboard.exists():
        raise SystemExit(f"dashboard ausente: {args.dashboard}")

    html = args.dashboard.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_TOKENS if token not in html)
    if missing:
        raise SystemExit(f"tokens ausentes: {missing}")
    if html.count('id="workflow-efficiency-visual-card"') != 1:
        raise SystemExit("card visual deve existir exatamente uma vez")
    if html.count("function renderWorkflowEfficiency(payload)") != 1:
        raise SystemExit("função de renderização deve existir exatamente uma vez")
    if "fetch('http" in html or 'fetch("http' in html:
        raise SystemExit("cards não podem introduzir chamadas externas")

    try:
        advisor = validate_advisor(args.dashboard, args.runtime_index)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "status": "passed",
        "cards": ["workflow_efficiency", "executive_promotion_advisor"],
        "source": "runtime-executive-index.json",
        "advisor_contract_validated": advisor["contract_validated"],
        "production_blocker": False,
        "human_approval_required": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
