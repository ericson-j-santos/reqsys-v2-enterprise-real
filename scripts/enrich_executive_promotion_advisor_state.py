#!/usr/bin/env python3
"""Consolida o Executive Promotion Advisor no Estado Único e Executive Brief.

Modo report-only: não altera deploy, merge queue, auto-merge, branch protection
nem a decisão global de produção.
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


def summarize(advisor: dict[str, Any]) -> dict[str, Any]:
    decision = str(advisor.get("decision") or "REVIEW").upper()
    confidence = float(advisor.get("confidence_percent") or 0)
    return {
        "available": bool(advisor),
        "decision": decision,
        "status": "green" if decision == "READY" else "yellow" if decision == "REVIEW" else "red",
        "confidence_percent": confidence,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "risk_domains": list(advisor.get("risk_domains") or []),
        "recommendation": advisor.get("recommendation"),
        "correlation_id": advisor.get("correlation_id"),
        "generated_at": advisor.get("generated_at"),
        "inputs": dict(advisor.get("inputs") or {}),
    }


def enrich_runtime(index: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    summary = dict(payload.get("summary") or {})
    cards = dict(payload.get("cards") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    cards["executive_promotion_advisor"] = card
    summary["executive_promotion_advisor_decision"] = card["decision"]
    summary["executive_promotion_advisor_confidence_percent"] = card["confidence_percent"]
    summary["executive_promotion_requires_human_approval"] = True
    links["executive_promotion_advisor"] = "artifacts/executive-promotion-advisor/executive-promotion-advisor.json"

    marker = "executive_promotion_advisor_report_only"
    if marker not in guardrails:
        guardrails.append(marker)

    payload["schema_version"] = "1.5.0"
    payload["summary"] = summary
    payload["cards"] = cards
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_brief(brief: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    evidences = dict(payload.get("evidencias") or {})
    semaforo = dict(payload.get("semaforo_executivo") or {})

    indicators["executive_promotion_advisor_decision"] = card["decision"]
    indicators["executive_promotion_advisor_confidence_percent"] = card["confidence_percent"]
    indicators["executive_promotion_risk_domain_count"] = len(card["risk_domains"])
    indicators["executive_promotion_human_approval_required"] = True
    evidences["executive_promotion_advisor"] = card
    semaforo["executive_promotion_advisor"] = card["status"]

    payload["indicadores"] = indicators
    payload["evidencias"] = evidences
    payload["semaforo_executivo"] = semaforo
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida Executive Promotion Advisor no Estado Único")
    parser.add_argument("--advisor", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    args = parser.parse_args()

    advisor = load_json(args.advisor)
    if not advisor:
        raise SystemExit("advisor ausente ou inválido")

    card = summarize(advisor)
    write_json(args.runtime_index, enrich_runtime(load_json(args.runtime_index), card))
    write_json(args.executive_brief, enrich_brief(load_json(args.executive_brief), card))

    print(json.dumps({
        "status": "enriched",
        "decision": card["decision"],
        "confidence_percent": card["confidence_percent"],
        "report_only": True,
        "production_blocker": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
