#!/usr/bin/env python3
"""Propaga o histórico público DEV/STG/PROD do Advisor ao Estado Único.

O enriquecimento é estritamente report-only e não altera readiness global,
produção, deploy ou gates bloqueantes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(history: dict[str, Any]) -> dict[str, Any]:
    environments = history.get("environments") or {}
    comparison: dict[str, Any] = {}
    covered = 0
    total_samples = 0
    weighted_pass_sum = 0.0
    minimum_pass_rate = 100.0
    minimum_streak: int | None = None
    all_latest_passed = True

    for environment in ENVIRONMENTS:
        env_summary = ((environments.get(environment) or {}).get("summary") or {})
        sample_count = int(env_summary.get("sample_count") or 0)
        pass_rate = float(env_summary.get("pass_rate_percent") or 0)
        stable_streak = int(env_summary.get("stable_streak") or 0)
        latest_status = str(env_summary.get("latest_status") or "unknown")
        latest_decision = str(env_summary.get("latest_decision") or "UNKNOWN")
        available = sample_count > 0
        if available:
            covered += 1
            total_samples += sample_count
            weighted_pass_sum += pass_rate * sample_count
            minimum_pass_rate = min(minimum_pass_rate, pass_rate)
            minimum_streak = stable_streak if minimum_streak is None else min(minimum_streak, stable_streak)
        all_latest_passed = all_latest_passed and available and latest_status == "passed"
        comparison[environment] = {
            "available": available,
            "sample_count": sample_count,
            "pass_rate_percent": pass_rate,
            "stable_streak": stable_streak,
            "latest_status": latest_status,
            "latest_decision": latest_decision,
            "eligible_for_human_review": bool(env_summary.get("eligible_for_human_review")),
            "production_blocker": False,
        }

    weighted_pass_rate = round(weighted_pass_sum / total_samples, 2) if total_samples else 0.0
    full_coverage = covered == len(ENVIRONMENTS)
    eligible = (
        full_coverage
        and all_latest_passed
        and total_samples >= 30
        and minimum_pass_rate >= 98
        and (minimum_streak or 0) >= 10
    )
    if not full_coverage:
        trend = "insufficient-environment-coverage"
    elif eligible:
        trend = "eligible-for-human-review"
    elif all_latest_passed and minimum_pass_rate >= 98:
        trend = "stable"
    elif weighted_pass_rate >= 90:
        trend = "improving"
    else:
        trend = "attention"

    return {
        "available": bool(history),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "environment_order": list(ENVIRONMENTS),
        "environment_count": covered,
        "full_environment_coverage": full_coverage,
        "sample_count": total_samples,
        "weighted_pass_rate_percent": weighted_pass_rate,
        "minimum_pass_rate_percent": minimum_pass_rate if covered else 0.0,
        "minimum_stable_streak": minimum_streak or 0,
        "all_latest_passed": all_latest_passed,
        "eligible_for_gate_review": eligible,
        "trend": trend,
        "generated_at": history.get("generated_at"),
        "source": "executive-promotion-advisor-public-smoke-history/history.json",
        "environments": comparison,
    }


def enrich_runtime_index(index: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    cards = dict(payload.get("cards") or {})
    summary = dict(payload.get("summary") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    cards["executive_promotion_advisor_public_smoke_comparison"] = card
    summary["advisor_public_smoke_environment_count"] = card["environment_count"]
    summary["advisor_public_smoke_sample_count"] = card["sample_count"]
    summary["advisor_public_smoke_weighted_pass_rate_percent"] = card["weighted_pass_rate_percent"]
    summary["advisor_public_smoke_full_environment_coverage"] = card["full_environment_coverage"]
    summary["advisor_public_smoke_gate_review_eligible"] = card["eligible_for_gate_review"]
    links["executive_promotion_advisor_public_smoke_history"] = card["source"]

    guardrail = "executive_promotion_advisor_public_smoke_comparison_report_only"
    if guardrail not in guardrails:
        guardrails.append(guardrail)

    payload["cards"] = cards
    payload["summary"] = summary
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_executive_brief(brief: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    semaforo = dict(payload.get("semaforo_executivo") or {})
    evidences = dict(payload.get("evidencias") or {})

    indicators["advisor_public_smoke_environment_count"] = card["environment_count"]
    indicators["advisor_public_smoke_sample_count"] = card["sample_count"]
    indicators["advisor_public_smoke_weighted_pass_rate_percent"] = card["weighted_pass_rate_percent"]
    indicators["advisor_public_smoke_minimum_pass_rate_percent"] = card["minimum_pass_rate_percent"]
    indicators["advisor_public_smoke_minimum_stable_streak"] = card["minimum_stable_streak"]
    indicators["advisor_public_smoke_full_environment_coverage"] = card["full_environment_coverage"]
    indicators["advisor_public_smoke_gate_review_eligible"] = card["eligible_for_gate_review"]

    if card["eligible_for_gate_review"]:
        semaphore = "green"
    elif card["trend"] in {"stable", "improving"}:
        semaphore = "yellow"
    else:
        semaphore = "red" if card["sample_count"] else "gray"

    semaforo["executive_promotion_advisor_public_smoke_comparison"] = semaphore
    evidences["executive_promotion_advisor_public_smoke_comparison"] = card
    payload["indicadores"] = indicators
    payload["semaforo_executivo"] = semaforo
    payload["evidencias"] = evidences
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara smoke público DEV/STG/PROD do Advisor")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    args = parser.parse_args()

    history = load_json(args.history)
    if not history:
        raise SystemExit("histórico público ausente ou vazio")
    if history.get("mode") != "report-only":
        raise SystemExit("histórico inválido: mode deve ser report-only")
    if history.get("production_blocker") is not False:
        raise SystemExit("histórico inválido: production_blocker deve ser false")
    if history.get("human_approval_required") is not True:
        raise SystemExit("histórico inválido: human_approval_required deve ser true")

    card = summarize(history)
    write_json(args.runtime_index, enrich_runtime_index(load_json(args.runtime_index), card))
    write_json(args.executive_brief, enrich_executive_brief(load_json(args.executive_brief), card))
    print(json.dumps({
        "status": "enriched",
        "trend": card["trend"],
        "environment_count": card["environment_count"],
        "sample_count": card["sample_count"],
        "eligible_for_gate_review": card["eligible_for_gate_review"],
        "mode": "report-only",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
