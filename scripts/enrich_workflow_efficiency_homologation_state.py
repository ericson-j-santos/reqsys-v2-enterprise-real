#!/usr/bin/env python3
"""Integra a homologação do Workflow Efficiency ao Estado Único e ao readiness.

Modo report-only: a evidência é publicada nos contratos executivos, mas não altera
a decisão de produção nem cria bloqueio automático.
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


def summarize(evidence: dict[str, Any]) -> dict[str, Any]:
    status = str(evidence.get("status") or "unknown").lower()
    decision = str(evidence.get("decision") or "UNKNOWN").upper()
    checks = evidence.get("checks") or {}
    errors = evidence.get("errors") or []
    details = evidence.get("workflow_efficiency") or {}
    homologated = status == "passed" and decision == "HOMOLOGATED"
    return {
        "available": bool(evidence),
        "status": status,
        "decision": decision,
        "homologated": homologated,
        "artifact_valid": homologated,
        "report_only": True,
        "production_blocker": False,
        "correlation_id": evidence.get("correlation_id"),
        "generated_at": evidence.get("generated_at"),
        "source": evidence.get("source") or "ops-dashboard-static",
        "score_percent": details.get("score_percent"),
        "mode": details.get("mode") or "report-only",
        "link": details.get("link"),
        "html_sha256": checks.get("html_sha256"),
        "contract_sha256": checks.get("contract_sha256"),
        "error_count": len(errors),
        "errors": errors,
    }


def enrich_runtime_index(index: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    summary = dict(payload.get("summary") or {})
    cards = dict(payload.get("cards") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    cards["workflow_efficiency_homologation"] = card
    summary["workflow_efficiency_homologated"] = bool(card["homologated"])
    summary["workflow_efficiency_homologation_status"] = card["status"]
    links["workflow_efficiency_homologation"] = "artifacts/workflow-efficiency-artifact-homologation/evidence.json"
    guardrail = "workflow_efficiency_homologation_report_only"
    if guardrail not in guardrails:
        guardrails.append(guardrail)

    payload["schema_version"] = "1.3.0"
    payload["summary"] = summary
    payload["cards"] = cards
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_executive_brief(brief: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    semaforo = dict(payload.get("semaforo_executivo") or {})
    evidences = dict(payload.get("evidencias") or {})

    indicators["workflow_efficiency_homologated"] = bool(card["homologated"])
    indicators["workflow_efficiency_homologation_error_count"] = card["error_count"]
    semaforo["workflow_efficiency_homologation"] = "green" if card["homologated"] else "yellow"
    evidences["workflow_efficiency_homologation"] = card

    payload["indicadores"] = indicators
    payload["semaforo_executivo"] = semaforo
    payload["evidencias"] = evidences
    return payload


def enrich_readiness(gate: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(gate)
    domains = dict(payload.get("domains") or {})
    domains["workflow_efficiency_homologation"] = {
        "id": "workflow_efficiency_homologation",
        "label": "Homologação Workflow Efficiency",
        "state": "green" if card["homologated"] else "yellow",
        "score": 100 if card["homologated"] else 70,
        "available": card["available"],
        "detail": f"decision={card['decision']}; errors={card['error_count']}; report_only=true",
        "production_blocker": False,
        "report_only": True,
        "correlation_id": card.get("correlation_id"),
    }
    payload["domains"] = domains

    readiness = dict(payload.get("executive_readiness") or {})
    observations = list(readiness.get("observations") or [])
    observation = "workflow_efficiency_homologation_report_only"
    if observation not in observations:
        observations.append(observation)
    readiness["observations"] = observations
    readiness["workflow_efficiency_homologated"] = bool(card["homologated"])
    payload["executive_readiness"] = readiness
    payload["schema_version"] = "1.1.0"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Integra homologação Workflow Efficiency ao Estado Único")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    parser.add_argument("--executive-readiness", type=Path, required=True)
    args = parser.parse_args()

    evidence = load_json(args.evidence)
    if not evidence:
        raise SystemExit("evidência de homologação ausente ou vazia")

    card = summarize(evidence)
    write_json(args.runtime_index, enrich_runtime_index(load_json(args.runtime_index), card))
    write_json(args.executive_brief, enrich_executive_brief(load_json(args.executive_brief), card))
    write_json(args.executive_readiness, enrich_readiness(load_json(args.executive_readiness), card))

    print(json.dumps({
        "status": "enriched",
        "homologated": card["homologated"],
        "report_only": True,
        "correlation_id": card.get("correlation_id"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
