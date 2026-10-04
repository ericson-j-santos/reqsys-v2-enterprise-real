#!/usr/bin/env python3
"""Enriquece o Runtime Executive Index com o Executive Readiness Gate.

Pós-processador offline e idempotente. Não altera o builder principal, reduzindo
conflitos com merges paralelos e mantendo o contrato público centralizado em
`runtime-executive-index.json`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize(value: Any, default: str = "unknown") -> str:
    return str(value if value is not None else default).strip().lower() or default


def to_risk(decision: str, ready: bool, blockers: list[Any], risk_percent: int) -> str:
    if blockers or not ready or normalize(decision) == "blocked_for_production":
        return "high"
    if risk_percent <= 15:
        return "low"
    if risk_percent <= 35:
        return "medium"
    return "high"


def summarize_gate(gate: dict[str, Any]) -> dict[str, Any]:
    readiness = gate.get("executive_readiness") or {}
    domains = gate.get("domains") or {}
    blockers = readiness.get("blockers") or []
    score = int(readiness.get("score") or 0)
    risk_percent = int(readiness.get("risk_percent") or max(0, 100 - score))
    decision = readiness.get("decision") or "UNKNOWN"
    ready = bool(readiness.get("ready_for_production"))
    status = normalize(readiness.get("overall_state"), "green" if ready else "red")
    return {
        "available": bool(gate),
        "status": status,
        "decision": str(decision).upper(),
        "ready_for_production": ready,
        "score": score,
        "risk_percent": risk_percent,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "domain_count": len(domains),
        "required_domains": [
            key for key, value in domains.items()
            if isinstance(value, dict) and value.get("production_blocker")
        ],
        "risk": to_risk(str(decision), ready, blockers, risk_percent),
        "source_artifact": "executive-readiness-gate",
    }


def enrich(index: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    summary = dict(payload.get("summary") or {})
    cards = dict(payload.get("cards") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    readiness = summarize_gate(gate)
    cards["executive_readiness"] = readiness
    summary["production_ready"] = bool(readiness["ready_for_production"])
    summary["executive_readiness_decision"] = readiness["decision"]
    if readiness["available"] and readiness["risk"] == "high":
        summary["status"] = "critical"
        summary["risk"] = "high"
    elif readiness["available"] and readiness["ready_for_production"] and summary.get("risk") == "low":
        summary["status"] = "passed"

    links["executive_readiness_gate"] = "artifacts/executive-readiness-gate/executive-readiness-gate.json"
    if "executive_readiness_gate_precedence_for_production_decision" not in guardrails:
        guardrails.append("executive_readiness_gate_precedence_for_production_decision")

    payload["schema_version"] = "1.2.0"
    payload["summary"] = summary
    payload["cards"] = cards
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich Runtime Executive Index with Executive Readiness Gate")
    parser.add_argument("--runtime-index", type=Path, default=Path("docs/ops-dashboard/data/runtime-executive-index.json"))
    parser.add_argument("--executive-readiness", type=Path, default=Path("artifacts/executive-readiness-gate/executive-readiness-gate.json"))
    args = parser.parse_args()

    index = load_json(args.runtime_index)
    gate = load_json(args.executive_readiness)
    enriched = enrich(index, gate)
    args.runtime_index.parent.mkdir(parents=True, exist_ok=True)
    args.runtime_index.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "enriched", "schema_version": enriched.get("schema_version"), "decision": enriched.get("summary", {}).get("executive_readiness_decision")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
