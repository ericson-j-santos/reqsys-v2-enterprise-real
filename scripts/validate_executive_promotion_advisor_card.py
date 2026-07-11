#!/usr/bin/env python3
"""Valida o card do Executive Promotion Advisor em dashboard fonte ou artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_TOKENS = {
    'id="executive-promotion-advisor-card"',
    'id="promotion-advisor-decision"',
    'id="promotion-advisor-confidence"',
    'id="promotion-advisor-risks"',
    'id="promotion-advisor-human-gate"',
    'function renderExecutivePromotionAdvisor(payload)',
    'renderExecutivePromotionAdvisor(payload);',
    'payload?.cards?.executive_promotion_advisor',
}


def validate(dashboard: Path, runtime_index: Path | None = None) -> dict[str, object]:
    if not dashboard.is_file():
        raise ValueError(f"dashboard ausente: {dashboard}")

    html = dashboard.read_text(encoding="utf-8")
    missing = sorted(token for token in REQUIRED_TOKENS if token not in html)
    if missing:
        raise ValueError(f"tokens ausentes: {missing}")
    if html.count('id="executive-promotion-advisor-card"') != 1:
        raise ValueError("card deve existir exatamente uma vez")
    if html.count("function renderExecutivePromotionAdvisor(payload)") != 1:
        raise ValueError("função deve existir exatamente uma vez")
    if "fetch('http" in html or 'fetch("http' in html:
        raise ValueError("card não pode introduzir chamadas externas")

    contract = None
    if runtime_index is not None:
        payload = json.loads(runtime_index.read_text(encoding="utf-8"))
        contract = (payload.get("cards") or {}).get("executive_promotion_advisor")
        if not isinstance(contract, dict) or not contract:
            raise ValueError("cards.executive_promotion_advisor ausente")
        if contract.get("mode") != "report-only":
            raise ValueError("advisor deve permanecer report-only")
        if contract.get("production_blocker") is not False:
            raise ValueError("advisor não pode bloquear produção automaticamente")
        if contract.get("human_approval_required") is not True:
            raise ValueError("aprovação humana deve ser obrigatória")

    return {
        "status": "passed",
        "card": "executive_promotion_advisor",
        "contract_validated": contract is not None,
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    parser.add_argument("--runtime-index", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = validate(args.dashboard, args.runtime_index)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
