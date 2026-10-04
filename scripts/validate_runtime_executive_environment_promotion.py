#!/usr/bin/env python3
"""Valida integração do Environment Promotion Readiness ao Runtime Executive Index."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RUNTIME_INDEX = Path("docs/ops-dashboard/data/runtime-executive-index.json")
DASHBOARD_COPY = Path("docs/ops-dashboard/data/environment-promotion-readiness.json")
REQUIRED_ENVS = {"dev", "stg", "prod"}
VALID_DECISIONS = {"READY_FOR_PROD_PROMOTION", "BLOCKED_FOR_PROD_PROMOTION", "UNKNOWN"}


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    index = load_json(RUNTIME_INDEX)
    if not index:
        return fail(f"arquivo ausente ou inválido: {RUNTIME_INDEX}")

    card = (index.get("cards") or {}).get("environment_promotion_readiness")
    if not isinstance(card, dict):
        return fail("cards.environment_promotion_readiness ausente")

    if card.get("decision") not in VALID_DECISIONS:
        return fail("decision de promoção inválida")

    if "ready_for_prod_promotion" not in card:
        return fail("ready_for_prod_promotion ausente")

    if set(card.get("required_environments") or []) != REQUIRED_ENVS:
        return fail("required_environments deve conter dev, stg e prod")

    if not isinstance(card.get("production_blockers"), list):
        return fail("production_blockers deve ser lista")

    summary = index.get("summary") or {}
    if summary.get("environment_promotion_decision") != card.get("decision"):
        return fail("summary.environment_promotion_decision divergente do card")

    links = index.get("links") or {}
    if links.get("environment_promotion_readiness") != "data/environment-promotion-readiness.json":
        return fail("link estático de environment_promotion_readiness ausente")

    guardrails = set(index.get("guardrails") or [])
    if "environment_promotion_readiness_required_before_prod_release" not in guardrails:
        return fail("guardrail de promoção produtiva ausente")

    if card.get("available") and not DASHBOARD_COPY.exists():
        return fail(f"cópia pública ausente: {DASHBOARD_COPY}")

    print(json.dumps({
        "status": "passed",
        "decision": card.get("decision"),
        "ready": card.get("ready_for_prod_promotion"),
        "coverage_percent": card.get("coverage_percent"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
