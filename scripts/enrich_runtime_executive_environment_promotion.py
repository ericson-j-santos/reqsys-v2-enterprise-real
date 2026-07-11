#!/usr/bin/env python3
"""Enriquece o Runtime Executive Index com Environment Promotion Readiness.

Pós-processador offline, idempotente e report-only. O runtime público consome
somente o JSON estático enriquecido, sem chamadas externas e sem secrets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_RUNTIME_INDEX = Path("docs/ops-dashboard/data/runtime-executive-index.json")
DEFAULT_READINESS = Path("artifacts/environment-promotion-readiness/environment-promotion-readiness.json")
DEFAULT_DASHBOARD_COPY = Path("docs/ops-dashboard/data/environment-promotion-readiness.json")


READY_DECISION = "READY_FOR_PROD_PROMOTION"
BLOCKED_DECISION = "BLOCKED_FOR_PROD_PROMOTION"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize(value: Any, default: str = "unknown") -> str:
    return str(value if value is not None else default).strip().lower() or default


def summarize_environment_promotion(readiness: dict[str, Any]) -> dict[str, Any]:
    coverage = readiness.get("coverage") or {}
    blockers = readiness.get("production_blockers") or []
    envs = readiness.get("environments") or []
    decision = str(readiness.get("decision") or "UNKNOWN").upper()
    ready = bool(readiness.get("ready_for_prod_promotion"))
    coverage_percent = float(coverage.get("coverage_percent") or 0)

    if ready and decision == READY_DECISION:
        status = "green"
        risk = "low"
    elif readiness:
        status = "red"
        risk = "high"
    else:
        status = "unknown"
        risk = "medium"

    return {
        "available": bool(readiness),
        "status": status,
        "risk": risk,
        "decision": decision,
        "ready_for_prod_promotion": ready,
        "coverage_percent": coverage_percent,
        "required_environments": coverage.get("required_environments") or ["dev", "stg", "prod"],
        "ready_environments": coverage.get("ready_environments") or [],
        "missing_environments": coverage.get("missing_environments") or [],
        "failed_environments": coverage.get("failed_environments") or [],
        "environment_count": len(envs),
        "blocker_count": len(blockers),
        "production_blockers": blockers,
        "source_artifact": "environment-promotion-readiness",
        "mode": readiness.get("mode") or "report_only",
    }


def enrich(index: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    summary = dict(payload.get("summary") or {})
    cards = dict(payload.get("cards") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    promotion = summarize_environment_promotion(readiness)
    cards["environment_promotion_readiness"] = promotion
    links["environment_promotion_readiness"] = "data/environment-promotion-readiness.json"

    summary["environment_promotion_decision"] = promotion["decision"]
    summary["environment_promotion_ready"] = bool(promotion["ready_for_prod_promotion"])
    summary["environment_promotion_coverage_percent"] = promotion["coverage_percent"]

    if promotion["available"] and not promotion["ready_for_prod_promotion"]:
        summary["production_ready"] = False
        summary["status"] = "critical"
        summary["risk"] = "high"

    for guardrail in (
        "environment_promotion_readiness_required_before_prod_release",
        "dev_stg_prod_evidence_required_before_prod_promotion",
        "runtime_dashboard_consumes_static_promotion_readiness_only",
    ):
        if guardrail not in guardrails:
            guardrails.append(guardrail)

    payload["schema_version"] = "1.3.0"
    payload["summary"] = summary
    payload["cards"] = cards
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich Runtime Executive Index with Environment Promotion Readiness")
    parser.add_argument("--runtime-index", type=Path, default=DEFAULT_RUNTIME_INDEX)
    parser.add_argument("--environment-promotion-readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--dashboard-copy", type=Path, default=DEFAULT_DASHBOARD_COPY)
    args = parser.parse_args()

    index = load_json(args.runtime_index)
    readiness = load_json(args.environment_promotion_readiness)
    enriched = enrich(index, readiness)

    args.runtime_index.parent.mkdir(parents=True, exist_ok=True)
    args.runtime_index.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if readiness:
        args.dashboard_copy.parent.mkdir(parents=True, exist_ok=True)
        args.dashboard_copy.write_text(json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "enriched",
        "schema_version": enriched.get("schema_version"),
        "decision": enriched.get("summary", {}).get("environment_promotion_decision"),
        "ready": enriched.get("summary", {}).get("environment_promotion_ready"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
