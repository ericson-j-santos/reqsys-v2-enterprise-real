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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_current_score(
    *,
    from_evidence: bool,
    runtime_health_report: Path,
    delivery_maturity: Path,
) -> float:
    if not from_evidence:
        return CURRENT_TRILHA_D_SCORE
    runtime = _load_json(runtime_health_report)
    maturity = _load_json(delivery_maturity)
    candidates = [
        float(maturity.get("average_current_percent") or 0),
        float(runtime.get("maturity_percent") or 0),
        float((runtime.get("gold_standard_depth") or {}).get("overall_score") or 0),
    ]
    return clamp(max(candidates))


def build_payload(
    *,
    from_evidence: bool = False,
    runtime_health_report: Path | None = None,
    delivery_maturity: Path | None = None,
) -> dict[str, Any]:
    runtime_health_report = runtime_health_report or Path("artifacts/runtime-health-center/runtime-health-report.json")
    delivery_maturity = delivery_maturity or Path("audit/delivery-maturity/delivery-maturity-snapshot.json")
    current_score = round(resolve_current_score(
        from_evidence=from_evidence,
        runtime_health_report=runtime_health_report,
        delivery_maturity=delivery_maturity,
    ), 2)
    ranked = build_ranked_actions()
    recommended = [item for item in ranked if item["recommended_now"]]
    expected_gain_now = round(sum(float(item["expected_score_gain"]) for item in recommended), 2)
    projected_score = clamp(current_score + (0 if current_score >= 100 else expected_gain_now))
    gold_gap = round(max(TARGET_SCORE - current_score, 0), 2)
    bottleneck_dimension = "coverage" if current_score < 100 else "none"
    bottleneck_score = BASELINE_SIGNALS["coverage"] if current_score < 100 else 100.0

    state = "green" if (from_evidence and current_score >= TARGET_SCORE) or not from_evidence else "yellow"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "strategy": "pareto_operational_gold_base",
        "current_score": current_score,
        "target_score": TARGET_SCORE,
        "gold_gap": gold_gap,
        "projected_score_after_recommended": projected_score,
        "projected_gap_after_recommended": round(max(TARGET_SCORE - projected_score, 0), 2),
        "statistical_confidence": round(sum(float(item["confidence"]) for item in recommended) / len(recommended), 2) if recommended else 1.0,
        "dominant_bottleneck": {
            "dimension": bottleneck_dimension,
            "score": bottleneck_score,
            "gap_to_100": round(max(100.0 - bottleneck_score, 0), 2),
            "share_of_trilha_d_remaining_gap": 0.0 if current_score >= 100 else 1.0,
        },
        "summary": {
            "actions_evaluated": len(ranked),
            "recommended_now": 0 if current_score >= 100 else len(recommended),
            "expected_gain_now": 0 if current_score >= 100 else expected_gain_now,
            "pareto_rule": "2 ações recomendadas concentram maior relação impacto/risco/esforço",
            "next_increment": None if current_score >= 100 else (recommended[0]["id"] if recommended else None),
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
            "refresh_strategy": "evidence_driven_when_from_evidence_enabled" if from_evidence else "static_json_until_trilha_d_artifact_ingestion_is_enabled",
        },
    }


def write_payload(
    output_path: str,
    *,
    from_evidence: bool = False,
    runtime_health_report: Path | None = None,
    delivery_maturity: Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(
        from_evidence=from_evidence,
        runtime_health_report=runtime_health_report,
        delivery_maturity=delivery_maturity,
    )
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera índice Pareto da base operacional padrão ouro.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    parser.add_argument("--from-evidence", action="store_true", help="Deriva current_score de artifacts versionados")
    parser.add_argument("--runtime-health-report", default="artifacts/runtime-health-center/runtime-health-report.json")
    parser.add_argument("--delivery-maturity", default="audit/delivery-maturity/delivery-maturity-snapshot.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(
        args.output,
        from_evidence=args.from_evidence,
        runtime_health_report=Path(args.runtime_health_report),
        delivery_maturity=Path(args.delivery_maturity),
    )
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
