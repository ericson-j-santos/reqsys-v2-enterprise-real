#!/usr/bin/env python3
"""Build Padrão Ouro Operational Pareto Index.

Gera um índice estatístico para priorizar os poucos incrementos com maior impacto
na maturidade operacional padrão ouro.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json"
TARGET_SCORE = 98.0
CURRENT_TRILHA_D_SCORE = 95.88

BASELINE_SIGNALS = {
    "tests": 100.0,
    "coverage": 74.29,
    "mutation": 100.0,
    "contract": 100.0,
    "schema": 100.0,
    "ci-watch": 100.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def pareto_actions() -> list[dict[str, Any]]:
    return [
        {
            "id": "coverage_targeted_tests",
            "title": "Elevar coverage dos módulos críticos",
            "lane": "quality-governance",
            "dimension": "coverage",
            "current_score": BASELINE_SIGNALS["coverage"],
            "target_score": 82.0,
            "expected_score_gain": 3.85,
            "effort_points": 3,
            "risk": "low",
            "confidence": 0.82,
            "why_now": "coverage concentra 100% do gap restante da Trilha D contra 100 pontos",
            "next_artifacts": [
                "backend/tests/test_*_critical_paths.py",
                "docs/ops-dashboard/data/trilha-d-history.json",
            ],
        },
        {
            "id": "dashboard_trilha_d_history_card",
            "title": "Expor histórico da Trilha D no dashboard",
            "lane": "runtime-dashboard",
            "dimension": "operational-visibility",
            "current_score": 70.0,
            "target_score": 90.0,
            "expected_score_gain": 2.4,
            "effort_points": 2,
            "risk": "low",
            "confidence": 0.78,
            "why_now": "transforma evidência histórica em leitura operacional navegável",
            "next_artifacts": [
                "docs/ops-dashboard/data/trilha-d-history.json",
                "docs/ops-dashboard/index.html",
            ],
        },
        {
            "id": "artifact_ingestion_refresh",
            "title": "Automatizar refresh do histórico por artifact",
            "lane": "governance-automation",
            "dimension": "evidence-refresh",
            "current_score": 60.0,
            "target_score": 85.0,
            "expected_score_gain": 2.1,
            "effort_points": 5,
            "risk": "medium",
            "confidence": 0.7,
            "why_now": "reduz manutenção manual e aumenta confiabilidade temporal",
            "next_artifacts": [
                "scripts/build_trilha_d_history.py",
                ".github/workflows/trilha-d-qualidade-governanca.yml",
            ],
        },
        {
            "id": "predictive_regression_gate",
            "title": "Gate preditivo de regressão operacional",
            "lane": "predictive-governance",
            "dimension": "regression-risk",
            "current_score": 55.0,
            "target_score": 80.0,
            "expected_score_gain": 1.6,
            "effort_points": 5,
            "risk": "medium",
            "confidence": 0.64,
            "why_now": "usa tendência histórica para bloquear queda antes do merge",
            "next_artifacts": [
                "scripts/predict_operational_regression.py",
                "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json",
            ],
        },
    ]


def score_action(action: dict[str, Any]) -> float:
    gain = float(action["expected_score_gain"])
    confidence = float(action["confidence"])
    effort = max(float(action["effort_points"]), 1.0)
    risk_penalty = {"low": 1.0, "medium": 0.82, "high": 0.55}.get(action.get("risk"), 0.75)
    return round((gain * confidence * risk_penalty) / effort * 100, 2)


def build_ranked_actions() -> list[dict[str, Any]]:
    actions = pareto_actions()
    enriched = [{**action, "pareto_score": score_action(action)} for action in actions]
    enriched.sort(key=lambda item: item["pareto_score"], reverse=True)
    cumulative = 0.0
    total_gain = sum(float(item["expected_score_gain"]) for item in enriched) or 1.0
    for index, item in enumerate(enriched, start=1):
        cumulative += float(item["expected_score_gain"])
        item["rank"] = index
        item["cumulative_expected_gain_pct"] = round((cumulative / total_gain) * 100, 2)
        item["recommended_now"] = index <= 2
    return enriched


def build_payload() -> dict[str, Any]:
    ranked = build_ranked_actions()
    recommended = [item for item in ranked if item["recommended_now"]]
    expected_gain_now = round(sum(float(item["expected_score_gain"]) for item in recommended), 2)
    projected_score = clamp(CURRENT_TRILHA_D_SCORE + expected_gain_now)
    gold_gap = round(max(TARGET_SCORE - CURRENT_TRILHA_D_SCORE, 0), 2)

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": "green",
        "strategy": "pareto_operational_gold_base",
        "current_score": CURRENT_TRILHA_D_SCORE,
        "target_score": TARGET_SCORE,
        "gold_gap": gold_gap,
        "projected_score_after_recommended": projected_score,
        "projected_gap_after_recommended": round(max(TARGET_SCORE - projected_score, 0), 2),
        "statistical_confidence": round(sum(float(item["confidence"]) for item in recommended) / len(recommended), 2),
        "dominant_bottleneck": {
            "dimension": "coverage",
            "score": BASELINE_SIGNALS["coverage"],
            "gap_to_100": round(100.0 - BASELINE_SIGNALS["coverage"], 2),
            "share_of_trilha_d_remaining_gap": 1.0,
        },
        "summary": {
            "actions_evaluated": len(ranked),
            "recommended_now": len(recommended),
            "expected_gain_now": expected_gain_now,
            "pareto_rule": "2 ações recomendadas concentram maior relação impacto/risco/esforço",
            "next_increment": recommended[0]["id"] if recommended else None,
        },
        "links": {
            "trilha_d_history": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
            "actions": f"https://github.com/{REPO}/actions",
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_padrao_ouro_operational_pareto.py",
        },
        "ranked_actions": ranked,
        "runtime_dashboard_contract": {
            "card_fields": ["state", "current_score", "target_score", "gold_gap", "projected_score_after_recommended"],
            "ranking_fields": ["rank", "title", "pareto_score", "expected_score_gain", "confidence", "risk", "recommended_now"],
            "bottleneck_fields": ["dimension", "score", "gap_to_100", "share_of_trilha_d_remaining_gap"],
            "refresh_strategy": "static_json_until_trilha_d_artifact_ingestion_is_enabled",
        },
    }


def write_payload(output_path: str) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera índice Pareto da base operacional padrão ouro.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "operational_pareto_state="
            f"{payload['state']} current={payload['current_score']} "
            f"projected={payload['projected_score_after_recommended']} "
            f"output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
