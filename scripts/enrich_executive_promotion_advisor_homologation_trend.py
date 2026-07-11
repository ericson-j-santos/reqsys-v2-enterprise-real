#!/usr/bin/env python3
"""Propaga a tendência de homologação do Executive Promotion Advisor.

O enriquecimento é estritamente report-only: não altera readiness global,
produção, deploy ou qualquer gate bloqueante.
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


def summarize(history: dict[str, Any]) -> dict[str, Any]:
    summary = history.get("summary") or {}
    sample_count = int(summary.get("sample_count") or 0)
    homologation_rate = float(summary.get("full_homologation_rate_percent") or 0)
    stable_streak = int(summary.get("stable_streak") or 0)
    eligible = bool(summary.get("eligible_for_gate_review"))

    if sample_count == 0:
        trend = "insufficient-data"
    elif eligible:
        trend = "eligible-for-human-review"
    elif homologation_rate >= 98 and stable_streak > 0:
        trend = "stable"
    elif homologation_rate >= 90:
        trend = "improving"
    else:
        trend = "attention"

    return {
        "available": bool(history),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "sample_count": sample_count,
        "artifact_pass_rate_percent": float(summary.get("artifact_pass_rate_percent") or 0),
        "public_pass_rate_percent": float(summary.get("public_pass_rate_percent") or 0),
        "full_homologation_rate_percent": homologation_rate,
        "stable_streak": stable_streak,
        "latest_decision": str(summary.get("latest_decision") or "UNKNOWN"),
        "eligible_for_gate_review": eligible,
        "trend": trend,
        "generated_at": history.get("generated_at"),
        "source": "executive-promotion-advisor-homologation-history/history.json",
    }


def enrich_runtime_index(index: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    cards = dict(payload.get("cards") or {})
    summary = dict(payload.get("summary") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    cards["executive_promotion_advisor_homologation_trend"] = trend
    summary["executive_promotion_advisor_homologation_sample_count"] = trend["sample_count"]
    summary["executive_promotion_advisor_homologation_rate_percent"] = trend[
        "full_homologation_rate_percent"
    ]
    summary["executive_promotion_advisor_gate_review_eligible"] = trend[
        "eligible_for_gate_review"
    ]
    links["executive_promotion_advisor_homologation_history"] = trend["source"]

    guardrail = "executive_promotion_advisor_homologation_trend_report_only"
    if guardrail not in guardrails:
        guardrails.append(guardrail)

    payload["cards"] = cards
    payload["summary"] = summary
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_executive_brief(brief: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    semaforo = dict(payload.get("semaforo_executivo") or {})
    evidences = dict(payload.get("evidencias") or {})

    indicators["advisor_homologation_sample_count"] = trend["sample_count"]
    indicators["advisor_homologation_rate_percent"] = trend[
        "full_homologation_rate_percent"
    ]
    indicators["advisor_homologation_stable_streak"] = trend["stable_streak"]
    indicators["advisor_gate_review_eligible"] = trend["eligible_for_gate_review"]

    if trend["eligible_for_gate_review"]:
        semaphore = "green"
    elif trend["trend"] in {"stable", "improving"}:
        semaphore = "yellow"
    else:
        semaphore = "red" if trend["sample_count"] else "gray"

    semaforo["executive_promotion_advisor_homologation_trend"] = semaphore
    evidences["executive_promotion_advisor_homologation_trend"] = trend

    payload["indicadores"] = indicators
    payload["semaforo_executivo"] = semaforo
    payload["evidencias"] = evidences
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Propaga tendência do Advisor ao Estado Único")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    args = parser.parse_args()

    history = load_json(args.history)
    if not history:
        raise SystemExit("histórico de homologação ausente ou vazio")
    if history.get("mode") != "report-only":
        raise SystemExit("histórico inválido: mode deve ser report-only")
    if (history.get("summary") or {}).get("production_blocker") is not False:
        raise SystemExit("histórico inválido: production_blocker deve ser false")

    trend = summarize(history)
    write_json(args.runtime_index, enrich_runtime_index(load_json(args.runtime_index), trend))
    write_json(args.executive_brief, enrich_executive_brief(load_json(args.executive_brief), trend))

    print(json.dumps({
        "status": "enriched",
        "trend": trend["trend"],
        "sample_count": trend["sample_count"],
        "eligible_for_gate_review": trend["eligible_for_gate_review"],
        "mode": "report-only",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
