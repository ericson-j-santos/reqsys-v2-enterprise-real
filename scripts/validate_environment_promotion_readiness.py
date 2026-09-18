#!/usr/bin/env python3
"""Validate DEV→STG→PROD environment promotion readiness contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path("artifacts/environment-promotion-readiness/environment-promotion-readiness.json")
REQUIRED_ENVS = {"dev", "stg", "prod"}


def fail(message: str) -> int:
    print(f"ERRO: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not DEFAULT_PATH.exists():
        return fail(f"arquivo ausente: {DEFAULT_PATH}")
    payload = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        return fail("schema_version deve ser 1.0.0")
    if payload.get("kind") != "environment_promotion_readiness":
        return fail("kind inválido")
    if payload.get("decision") not in {"READY_FOR_PROD_PROMOTION", "BLOCKED_FOR_PROD_PROMOTION"}:
        return fail("decision inválida")
    if "ready_for_prod_promotion" not in payload:
        return fail("ready_for_prod_promotion ausente")
    envs = payload.get("environments") or []
    observed = {item.get("environment") for item in envs}
    if observed != REQUIRED_ENVS:
        return fail(f"ambientes esperados {sorted(REQUIRED_ENVS)}, obtido {sorted(observed)}")
    coverage = payload.get("coverage") or {}
    if set(coverage.get("required_environments") or []) != REQUIRED_ENVS:
        return fail("coverage.required_environments inválido")
    if not isinstance(payload.get("production_blockers"), list):
        return fail("production_blockers deve ser lista")
    guardrails = payload.get("guardrails") or []
    if "dev_stg_prod_required_before_prod_promotion" not in guardrails:
        return fail("guardrail DEV/STG/PROD ausente")
    print(json.dumps({"status": "passed", "decision": payload.get("decision"), "coverage_percent": coverage.get("coverage_percent")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
