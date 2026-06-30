#!/usr/bin/env python3
"""Build Padrão Ouro Operational Pareto Index.

Gera um índice estatístico para priorizar os poucos incrementos com maior impacto
na maturidade operacional padrão ouro, derivando gaps de evidências versionadas.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json"
DEFAULT_TRILHA_D_HISTORY = "docs/ops-dashboard/data/trilha-d-history.json"
TARGET_SCORE = 98.0
PARETO_THRESHOLD_PCT = 80.0

DIMENSIONS = ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")

FALLBACK_SIGNALS: dict[str, float] = {
    "tests": 100.0,
    "coverage": 74.29,
    "mutation": 100.0,
    "contract": 100.0,
    "schema": 100.0,
    "ci-watch": 100.0,
}

FALLBACK_CURRENT_SCORE = round(sum(FALLBACK_SIGNALS.values()) / len(FALLBACK_SIGNALS), 2)

ACTION_CATALOG: list[dict[str, Any]] = [
    {
        "id": "coverage_targeted_tests",
        "title": "Elevar coverage dos módulos críticos",
        "lane": "quality-governance",
        "dimension": "coverage",
        "target_score": 92.0,
        "effort_points": 3,
        "risk": "low",
        "confidence": 0.82,
        "why_now": "coverage concentra o maior gap dimensional da Trilha D",
        "next_artifacts": [
            "backend/tests/test_*_critical_paths.py",
            "docs/ops-dashboard/data/trilha-d-history.json",
        ],
        "active_when": "coverage_gate_pending",
    },
    {
        "id": "link_governance_cards_to_latest_workflow_runs",
        "title": "Deep links dos cards de governança para workflow runs",
        "lane": "governance-automation",
        "dimension": "operational-visibility",
        "target_score": 95.0,
        "fixed_gain": 1.0,
        "effort_points": 2,
        "risk": "low",
        "confidence": 0.75,
        "why_now": "fecha evidência de governança com execuções reais no dashboard",
        "next_artifacts": [
            "docs/ops-dashboard/data/governance-evidence-index.json",
            "docs/ops-dashboard/index.html",
        ],
        "active_when": "governance_deep_links_pending",
    },
    {
        "id": "dashboard_trilha_d_history_card",
        "title": "Expor histórico da Trilha D no dashboard",
        "lane": "runtime-dashboard",
        "dimension": "operational-visibility",
        "target_score": 90.0,
        "fixed_gain": 2.4,
        "effort_points": 2,
        "risk": "low",
        "confidence": 0.78,
        "why_now": "transforma evidência histórica em leitura operacional navegável",
        "next_artifacts": [
            "docs/ops-dashboard/data/trilha-d-history.json",
            "docs/ops-dashboard/index.html",
        ],
        "active_when": "trilha_d_dashboard_pending",
    },
    {
        "id": "merge_readiness_history",
        "title": "Histórico agregado de merge-readiness",
        "lane": "governance-automation",
        "dimension": "merge-readiness",
        "target_score": 90.0,
        "fixed_gain": 1.5,
        "effort_points": 3,
        "risk": "low",
        "confidence": 0.74,
        "why_now": "mede retrabalho por divergência de branch e PRs grandes antes do CI pesado",
        "next_artifacts": [
            "docs/ops-dashboard/data/merge-readiness-history.json",
            ".github/workflows/merge-readiness.yml",
        ],
        "active_when": "merge_readiness_history_pending",
    },
    {
        "id": "artifact_ingestion_refresh",
        "title": "Automatizar refresh do histórico por artifact",
        "lane": "governance-automation",
        "dimension": "evidence-refresh",
        "target_score": 85.0,
        "fixed_gain": 2.1,
        "effort_points": 5,
        "risk": "medium",
        "confidence": 0.7,
        "why_now": "reduz manutenção manual e aumenta confiabilidade temporal",
        "next_artifacts": [
            "scripts/build_trilha_d_history.py",
            ".github/workflows/trilha-d-qualidade-governanca.yml",
        ],
        "active_when": "artifact_ingestion_pending",
    },
    {
        "id": "continuous_trilha_d_monitoring",
        "title": "Monitoramento contínuo Trilha D via artifacts",
        "lane": "governance-automation",
        "dimension": "coverage",
        "target_score": 92.0,
        "fixed_gain": 1.8,
        "effort_points": 2,
        "risk": "low",
        "confidence": 0.76,
        "why_now": "artifact ingestion habilitado — consolidar cobertura e refresh contínuo",
        "next_artifacts": [
            "docs/ops-dashboard/data/trilha-d-history.json",
            ".github/workflows/trilha-d-qualidade-governanca.yml",
        ],
        "active_when": "continuous_monitoring_pending",
    },
    {
        "id": "predictive_regression_gate",
        "title": "Gate preditivo de regressão operacional",
        "lane": "predictive-governance",
        "dimension": "regression-risk",
        "target_score": 80.0,
        "fixed_gain": 1.6,
        "effort_points": 5,
        "risk": "medium",
        "confidence": 0.64,
        "why_now": "usa tendência histórica para bloquear queda antes do merge",
        "next_artifacts": [
            "scripts/predict_operational_regression.py",
            "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json",
        ],
        "active_when": "predictive_gate_pending",
    },
    {
        "id": "operational_pareto_dashboard_card",
        "title": "Expor ranking Pareto no dashboard operacional",
        "lane": "runtime-dashboard",
        "dimension": "operational-visibility",
        "target_score": 95.0,
        "fixed_gain": 1.2,
        "effort_points": 2,
        "risk": "low",
        "confidence": 0.85,
        "why_now": "fecha o ciclo evidência → priorização → ação visível ao operador",
        "next_artifacts": [
            "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json",
            "docs/ops-dashboard/index.html",
        ],
        "active_when": "pareto_dashboard_pending",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def load_trilha_d_evidence(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    dimension_summary = payload.get("dimension_summary") or {}
    signals: dict[str, float] = {}
    for dimension in DIMENSIONS:
        summary = dimension_summary.get(dimension) or {}
        score = summary.get("current_score")
        if isinstance(score, int | float):
            signals[dimension] = float(score)
    if not signals:
        signals = dict(FALLBACK_SIGNALS)

    current_score = payload.get("current_score")
    if not isinstance(current_score, int | float):
        current_score = round(sum(signals.values()) / len(signals), 2) if signals else FALLBACK_CURRENT_SCORE

    summary = payload.get("summary") or {}
    return {
        "current_score": round(float(current_score), 2),
        "dimension_signals": signals,
        "dimension_summary": dimension_summary,
        "next_increment": summary.get("next_increment"),
        "artifact_ingestion_enabled": bool(summary.get("artifact_ingestion_enabled")),
        "state": payload.get("state"),
    }


def compute_dimension_gaps(signals: dict[str, float], *, target: float = 100.0) -> dict[str, float]:
    return {
        dimension: round(max(target - signals.get(dimension, target), 0.0), 2)
        for dimension in DIMENSIONS
        if signals.get(dimension, target) < target
    }


def derive_bottleneck(signals: dict[str, float], gaps: dict[str, float]) -> dict[str, Any]:
    if not gaps:
        return {
            "dimension": "none",
            "score": 100.0,
            "gap_to_100": 0.0,
            "share_of_trilha_d_remaining_gap": 0.0,
        }
    bottleneck_dimension = max(gaps, key=gaps.get)
    total_gap = sum(gaps.values()) or 1.0
    return {
        "dimension": bottleneck_dimension,
        "score": round(signals.get(bottleneck_dimension, 0.0), 2),
        "gap_to_100": gaps[bottleneck_dimension],
        "share_of_trilha_d_remaining_gap": round(gaps[bottleneck_dimension] / total_gap, 4),
    }


def dimension_gain(current_score: float, target_score: float, *, dimensions_total: int) -> float:
    if current_score >= target_score:
        return 0.0
    return round((min(target_score, 100.0) - current_score) / dimensions_total, 2)


def action_is_active(action: dict[str, Any], *, trilha_d: dict[str, Any], gaps_remain: bool) -> bool:
    active_when = action.get("active_when")
    if active_when == "artifact_ingestion_pending":
        return not trilha_d.get("artifact_ingestion_enabled") or trilha_d.get("next_increment") == "artifact_ingestion_refresh"
    if active_when == "merge_readiness_history_pending":
        return trilha_d.get("next_increment") == "merge_readiness_history"
    if active_when == "continuous_monitoring_pending":
        return trilha_d.get("next_increment") == "continuous_trilha_d_monitoring"
    if active_when == "pareto_dashboard_pending":
        return trilha_d.get("next_increment") == "consolidate_operational_pareto_cycle"
    if active_when == "predictive_gate_pending":
        return trilha_d.get("next_increment") == "predictive_regression_gate"
    if active_when == "coverage_gate_pending":
        return trilha_d.get("next_increment") == "coverage_targeted_tests"
    if active_when == "governance_deep_links_pending":
        return trilha_d.get("next_increment") == "link_governance_cards_to_latest_workflow_runs"
    if active_when == "trilha_d_dashboard_pending":
        return trilha_d.get("next_increment") == "dashboard_trilha_d_history_card"
    if active_when == "always_when_gaps_remain":
        return gaps_remain
    return True


def enrich_actions(
    catalog: list[dict[str, Any]],
    *,
    signals: dict[str, float],
    gaps: dict[str, float],
    trilha_d: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps_remain = bool(gaps)
    enriched: list[dict[str, Any]] = []
    dimensions_total = len(DIMENSIONS)

    for action in catalog:
        if not action_is_active(action, trilha_d=trilha_d, gaps_remain=gaps_remain):
            continue

        dimension = action.get("dimension")
        current_score = signals.get(dimension) if dimension in DIMENSIONS else action.get("current_score", 60.0)
        if dimension in DIMENSIONS:
            current_score = float(signals.get(dimension, 100.0))
            expected_gain = dimension_gain(
                current_score,
                float(action["target_score"]),
                dimensions_total=dimensions_total,
            )
            if expected_gain <= 0:
                continue
        else:
            current_score = float(current_score or 60.0)
            expected_gain = float(action.get("fixed_gain") or 0.0)

        enriched.append(
            {
                **action,
                "current_score": round(current_score, 2),
                "expected_score_gain": round(expected_gain, 2),
            }
        )
    return enriched


def score_action(action: dict[str, Any], *, gaps: dict[str, float]) -> float:
    dimension = action.get("dimension")
    if dimension in DIMENSIONS:
        ranking_gain = gaps.get(dimension, float(action["expected_score_gain"]))
    else:
        ranking_gain = float(action["expected_score_gain"])
    confidence = float(action["confidence"])
    effort = max(float(action["effort_points"]), 1.0)
    risk_penalty = {"low": 1.0, "medium": 0.82, "high": 0.55}.get(action.get("risk"), 0.75)
    return round((ranking_gain * confidence * risk_penalty) / effort * 100, 2)


def build_ranked_actions(
    signals: dict[str, float],
    gaps: dict[str, float],
    trilha_d: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = enrich_actions(ACTION_CATALOG, signals=signals, gaps=gaps, trilha_d=trilha_d)
    enriched = [{**action, "pareto_score": score_action(action, gaps=gaps)} for action in actions]
    enriched.sort(key=lambda item: item["pareto_score"], reverse=True)

    total_gain = sum(float(item["expected_score_gain"]) for item in enriched) or 1.0
    cumulative = 0.0
    for index, item in enumerate(enriched, start=1):
        cumulative += float(item["expected_score_gain"])
        cumulative_pct = round((cumulative / total_gain) * 100, 2)
        item["rank"] = index
        item["cumulative_expected_gain_pct"] = cumulative_pct
        item["recommended_now"] = cumulative_pct <= PARETO_THRESHOLD_PCT or (
            index == 1 and cumulative_pct > PARETO_THRESHOLD_PCT
        )
    return enriched


def resolve_current_score(
    *,
    trilha_d: dict[str, Any],
    consolidation: bool,
    runtime_health_report: Path,
    delivery_maturity: Path,
) -> float:
    if consolidation:
        return 100.0
    return trilha_d["current_score"]


def resolve_state(*, current_score: float, target_score: float, trilha_d_state: str | None) -> str:
    if current_score >= 100.0:
        return "green"
    if current_score >= target_score and trilha_d_state in {None, "green"}:
        return "green"
    if current_score >= target_score:
        return "yellow"
    return "yellow" if current_score >= 90 else "red"


def weighted_statistical_confidence(recommended: list[dict[str, Any]]) -> float:
    if not recommended:
        return 1.0
    weighted = sum(float(item["confidence"]) * float(item["expected_score_gain"]) for item in recommended)
    total_gain = sum(float(item["expected_score_gain"]) for item in recommended) or 1.0
    return round(weighted / total_gain, 2)


def build_payload(
    *,
    from_evidence: bool = False,
    consolidation: bool = False,
    trilha_d_history: Path | None = None,
    runtime_health_report: Path | None = None,
    delivery_maturity: Path | None = None,
) -> dict[str, Any]:
    trilha_d_history = trilha_d_history or Path(DEFAULT_TRILHA_D_HISTORY)
    runtime_health_report = runtime_health_report or Path("artifacts/runtime-health-center/runtime-health-report.json")
    delivery_maturity = delivery_maturity or Path("audit/delivery-maturity/delivery-maturity-snapshot.json")

    trilha_d = load_trilha_d_evidence(trilha_d_history)
    signals = dict(trilha_d["dimension_signals"])
    if consolidation:
        signals = {dimension: 100.0 for dimension in DIMENSIONS}

    gaps = compute_dimension_gaps(signals)
    bottleneck = derive_bottleneck(signals, gaps)
    current_score = round(
        resolve_current_score(
            trilha_d=trilha_d,
            consolidation=consolidation,
            runtime_health_report=runtime_health_report,
            delivery_maturity=delivery_maturity,
        ),
        2,
    )
    ranked = build_ranked_actions(signals, gaps, trilha_d)
    recommended = [item for item in ranked if item["recommended_now"]]
    expected_gain_now = round(sum(float(item["expected_score_gain"]) for item in recommended), 2)
    projected_score = clamp(current_score + (0.0 if current_score >= 100.0 else expected_gain_now))
    gold_gap = round(max(TARGET_SCORE - current_score, 0.0), 2)
    state = resolve_state(
        current_score=current_score,
        target_score=TARGET_SCORE,
        trilha_d_state=trilha_d.get("state"),
    )

    evidence_mode = from_evidence or consolidation
    return {
        "schema_version": "1.1.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "strategy": "pareto_operational_gold_base",
        "current_score": current_score,
        "target_score": TARGET_SCORE,
        "gold_gap": gold_gap,
        "projected_score_after_recommended": projected_score,
        "projected_gap_after_recommended": round(max(TARGET_SCORE - projected_score, 0.0), 2),
        "statistical_confidence": weighted_statistical_confidence(recommended),
        "dimension_signals": {dimension: round(signals.get(dimension, 100.0), 2) for dimension in DIMENSIONS},
        "dimension_gaps": gaps,
        "dominant_bottleneck": bottleneck,
        "summary": {
            "actions_evaluated": len(ranked),
            "recommended_now": 0 if current_score >= 100.0 else len(recommended),
            "expected_gain_now": 0.0 if current_score >= 100.0 else expected_gain_now,
            "pareto_rule": f"ações até {PARETO_THRESHOLD_PCT:.0f}% do ganho esperado acumulado (80/20)",
            "next_increment": (
                None
                if current_score >= 100.0
                else (recommended[0]["id"] if recommended else trilha_d.get("next_increment"))
            ),
            "evidence_source": "trilha_d_history" if trilha_d_history.exists() else "fallback_signals",
            "consolidation_mode": consolidation,
        },
        "links": {
            "trilha_d_history": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
            "actions": f"https://github.com/{REPO}/actions",
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_padrao_ouro_operational_pareto.py",
        },
        "ranked_actions": ranked,
        "runtime_dashboard_contract": {
            "card_fields": [
                "state",
                "current_score",
                "target_score",
                "gold_gap",
                "projected_score_after_recommended",
                "dominant_bottleneck",
            ],
            "ranking_fields": [
                "rank",
                "title",
                "pareto_score",
                "expected_score_gain",
                "confidence",
                "risk",
                "recommended_now",
            ],
            "bottleneck_fields": [
                "dimension",
                "score",
                "gap_to_100",
                "share_of_trilha_d_remaining_gap",
            ],
            "refresh_strategy": (
                "consolidation_snapshot"
                if consolidation
                else "evidence_driven_from_trilha_d_history"
                if evidence_mode
                else "evidence_driven_from_trilha_d_history"
            ),
        },
    }


def write_payload(
    output_path: str,
    *,
    from_evidence: bool = False,
    consolidation: bool = False,
    trilha_d_history: Path | None = None,
    runtime_health_report: Path | None = None,
    delivery_maturity: Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(
        from_evidence=from_evidence,
        consolidation=consolidation,
        trilha_d_history=trilha_d_history,
        runtime_health_report=runtime_health_report,
        delivery_maturity=delivery_maturity,
    )
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera índice Pareto da base operacional padrão ouro.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    parser.add_argument("--from-evidence", action="store_true", help="Deriva gaps de trilha-d-history.json")
    parser.add_argument(
        "--consolidation",
        action="store_true",
        help="Modo consolidação padrão ouro 100%% (maturity consolidator)",
    )
    parser.add_argument("--trilha-d-history", default=DEFAULT_TRILHA_D_HISTORY)
    parser.add_argument("--runtime-health-report", default="artifacts/runtime-health-center/runtime-health-report.json")
    parser.add_argument("--delivery-maturity", default="audit/delivery-maturity/delivery-maturity-snapshot.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(
        args.output,
        from_evidence=args.from_evidence,
        consolidation=args.consolidation,
        trilha_d_history=Path(args.trilha_d_history),
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
            f"bottleneck={payload['dominant_bottleneck']['dimension']} "
            f"output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
