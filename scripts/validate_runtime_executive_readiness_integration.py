#!/usr/bin/env python3
"""Valida integração do Executive Readiness Gate ao Runtime Executive Index."""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_INDEX = Path("docs/ops-dashboard/data/runtime-executive-index.json")


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not DEFAULT_INDEX.exists():
        return fail(f"arquivo ausente: {DEFAULT_INDEX}")

    payload = json.loads(DEFAULT_INDEX.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.2.0":
        return fail("schema_version deve ser 1.2.0")

    summary = payload.get("summary") or {}
    cards = payload.get("cards") or {}
    links = payload.get("links") or {}
    guardrails = payload.get("guardrails") or []

    readiness = cards.get("executive_readiness") or {}
    if not readiness:
        return fail("cards.executive_readiness ausente")
    if "ready_for_production" not in readiness:
        return fail("cards.executive_readiness.ready_for_production ausente")
    if "decision" not in readiness:
        return fail("cards.executive_readiness.decision ausente")
    if summary.get("executive_readiness_decision") != readiness.get("decision"):
        return fail("summary.executive_readiness_decision divergente do card")
    if "production_ready" not in summary:
        return fail("summary.production_ready ausente")
    if not links.get("executive_readiness_gate"):
        return fail("links.executive_readiness_gate ausente")
    if "executive_readiness_gate_precedence_for_production_decision" not in guardrails:
        return fail("guardrail de precedência do readiness gate ausente")

    print(
        json.dumps(
            {
                "status": "passed",
                "schema_version": payload.get("schema_version"),
                "decision": readiness.get("decision"),
                "production_ready": summary.get("production_ready"),
                "score": readiness.get("score"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
