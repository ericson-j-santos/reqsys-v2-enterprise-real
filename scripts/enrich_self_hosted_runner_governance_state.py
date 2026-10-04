#!/usr/bin/env python3
"""Integra o guard de self-hosted runners ao Estado Único como sinal preventivo.

O contrato é estritamente report-only: não altera readiness global, produção,
branch protection, merge queue ou decisões humanas existentes.
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_card(evidence: dict[str, Any]) -> dict[str, Any]:
    usages = list(evidence.get("self_hosted_usages") or [])
    violations = list(evidence.get("violations") or [])
    policy = dict(evidence.get("policy") or {})
    evidence_status = str(evidence.get("status") or "unknown").lower()

    if violations:
        status = "attention"
        recommendation = "Revisar uso de self-hosted runner e regularizar política, ADR e allowlist."
    elif usages:
        status = "governed"
        recommendation = "Manter ADR, allowlist e atualização operacional do runner sob revisão humana."
    else:
        status = "not-in-use"
        recommendation = "Nenhuma ação imediata; preservar o guard preventivo."

    return {
        "available": bool(evidence),
        "status": status,
        "evidence_status": evidence_status,
        "self_hosted_in_use": bool(usages),
        "usage_count": len(usages),
        "violation_count": len(violations),
        "violations": violations,
        "policy_enabled": bool(policy.get("self_hosted_allowed", False)),
        "approved_workflow_count": len(policy.get("approved_workflows") or []),
        "required_adr": policy.get("required_adr"),
        "mode": "report-only",
        "severity": "P2" if not violations else "P1",
        "production_blocker": False,
        "human_approval_required": True,
        "recommendation": recommendation,
    }


def enrich_runtime(index: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    cards = dict(payload.get("cards") or {})
    summary = dict(payload.get("summary") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    cards["self_hosted_runner_governance"] = card
    summary["self_hosted_runner_governance_status"] = card["status"]
    summary["self_hosted_runner_governance_severity"] = card["severity"]
    summary["self_hosted_runner_in_use"] = card["self_hosted_in_use"]
    links["self_hosted_runner_governance"] = (
        "artifacts/self-hosted-runner-governance/self-hosted-runner-governance.json"
    )

    marker = "self_hosted_runner_governance_report_only"
    if marker not in guardrails:
        guardrails.append(marker)

    payload["cards"] = cards
    payload["summary"] = summary
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_brief(brief: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    evidences = dict(payload.get("evidencias") or {})
    semaforo = dict(payload.get("semaforo_executivo") or {})

    indicators["self_hosted_runner_governance_status"] = card["status"]
    indicators["self_hosted_runner_in_use"] = card["self_hosted_in_use"]
    indicators["self_hosted_runner_violation_count"] = card["violation_count"]
    evidences["self_hosted_runner_governance"] = card
    semaforo["self_hosted_runner_governance"] = (
        "yellow" if card["violation_count"] else "green"
    )

    payload["indicadores"] = indicators
    payload["evidencias"] = evidences
    payload["semaforo_executivo"] = semaforo
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Integra governança de self-hosted runner ao Estado Único")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    args = parser.parse_args()

    evidence = load_json(args.evidence)
    card = build_card(evidence)

    write_json(args.runtime_index, enrich_runtime(load_json(args.runtime_index), card))
    write_json(args.executive_brief, enrich_brief(load_json(args.executive_brief), card))

    print(json.dumps({
        "status": "enriched",
        "signal": card["status"],
        "severity": card["severity"],
        "report_only": True,
        "production_blocker": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
