#!/usr/bin/env python3
"""Build strategic governance index for executive prioritization.

The builder is deterministic, offline and report-only. It converts existing
runtime/merge/evidence artifacts into a single prioritization contract that can
be consumed by dashboards, agents and governed delivery routines without making
GitHub API calls at runtime.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def safe_number(*values: Any, default: float | int = 0) -> float | int:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            normalized = value.strip().replace("%", "").replace(",", ".")
            try:
                parsed = float(normalized)
                return int(parsed) if parsed.is_integer() else parsed
            except ValueError:
                continue
    return default


def normalize_status(value: Any, default: str = "unknown") -> str:
    return str(value or default).strip().lower() or default


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def risk_penalty(risk: Any) -> int:
    normalized = normalize_status(risk)
    if normalized in {"high", "critical", "failed", "failure", "blocked"}:
        return 35
    if normalized in {"medium", "warning", "degraded", "unknown"}:
        return 18
    return 5


def risk_level(score: float) -> str:
    if score >= 70:
        return "low"
    if score >= 45:
        return "medium"
    return "high"


def action_for_priority(priority_score: float, risk: str) -> str:
    if risk == "high":
        return "stabilizar_evidencias_antes_de_expandir"
    if priority_score >= 80:
        return "executar_agora"
    if priority_score >= 60:
        return "executar_no_proximo_lote"
    if priority_score >= 40:
        return "manter_no_backlog_governado"
    return "pausar_ou_reclassificar"


def classify_next_bottleneck(runtime_index: dict[str, Any]) -> dict[str, Any]:
    cards = runtime_index.get("cards") or {}
    readiness = cards.get("readiness") or {}
    merge_intelligence = cards.get("merge_intelligence") or {}
    evidence_gate = cards.get("evidence_gate") or {}
    finalization = cards.get("finalization") or {}

    if normalize_status(readiness.get("risk")) == "high":
        return {
            "name": "runtime_publico_e_readiness",
            "reason": "readiness_degraded_or_blocked",
            "recommended_increment": "runtime_readiness_consolidation",
        }
    if normalize_status(merge_intelligence.get("risk_level")) == "high":
        return {
            "name": "merge_governance_e_conflitos",
            "reason": "mergeability_or_conflict_risk_high",
            "recommended_increment": "merge_governance_self_healing",
        }
    if normalize_status(evidence_gate.get("risk")) != "low":
        return {
            "name": "evidencia_operacional",
            "reason": "evidence_gate_not_fully_green",
            "recommended_increment": "evidence_gate_consolidation",
        }
    if safe_number(finalization.get("residual_gap"), default=0) > 0:
        return {
            "name": "finalizacao_e_gaps_residuais",
            "reason": "delivery_finalization_gap_remaining",
            "recommended_increment": "delivery_finalization_gap_closure",
        }
    return {
        "name": "priorizacao_estrategica_e_consolidacao",
        "reason": "technical_flow_stable_enough_for_priority_optimization",
        "recommended_increment": "strategic_governance_engine",
    }


def build_lane_scores(runtime_index: dict[str, Any]) -> list[dict[str, Any]]:
    cards = runtime_index.get("cards") or {}
    summary = runtime_index.get("summary") or {}
    health = cards.get("health") or {}
    readiness = cards.get("readiness") or {}
    merge_intelligence = cards.get("merge_intelligence") or {}
    evidence_gate = cards.get("evidence_gate") or {}
    finalization = cards.get("finalization") or {}

    health_score = safe_number(health.get("score"), default=0)
    readiness_score = safe_number(readiness.get("readiness_percent"), default=0)
    merge_score = safe_number(merge_intelligence.get("mergeability_score"), default=0)
    executive_score = safe_number(summary.get("executive_score"), default=0)
    final_score = safe_number(finalization.get("final_score"), default=0)
    evidence_score = 100 if normalize_status(evidence_gate.get("risk")) == "low" else 60 if normalize_status(evidence_gate.get("risk")) == "medium" else 25

    lane_definitions = [
        {
            "lane": "runtime_readiness",
            "impact": 95,
            "autonomy_gain": 75,
            "cost_reduction": 65,
            "base_signal": readiness_score,
            "risk": readiness.get("risk"),
            "reason": "public_runtime_is_the_primary_user_value_gate",
        },
        {
            "lane": "merge_governance",
            "impact": 90,
            "autonomy_gain": 85,
            "cost_reduction": 80,
            "base_signal": merge_score,
            "risk": merge_intelligence.get("risk_level"),
            "reason": "mergeability_controls_delivery_throughput_and_conflict_cost",
        },
        {
            "lane": "evidence_governance",
            "impact": 85,
            "autonomy_gain": 70,
            "cost_reduction": 75,
            "base_signal": evidence_score,
            "risk": evidence_gate.get("risk"),
            "reason": "evidence_quality_controls_trust_and_autonomous_decision_safety",
        },
        {
            "lane": "delivery_finalization",
            "impact": 80,
            "autonomy_gain": 60,
            "cost_reduction": 70,
            "base_signal": final_score,
            "risk": finalization.get("risk"),
            "reason": "residual_gaps_prevent_claiming_consolidated_maturity",
        },
        {
            "lane": "system_health",
            "impact": 75,
            "autonomy_gain": 65,
            "cost_reduction": 70,
            "base_signal": health_score,
            "risk": health.get("risk"),
            "reason": "health_score_prevents_hidden_operational_debt",
        },
        {
            "lane": "strategic_prioritization",
            "impact": 88,
            "autonomy_gain": 90,
            "cost_reduction": 85,
            "base_signal": executive_score,
            "risk": summary.get("risk"),
            "reason": "priority_scoring_becomes_the_next_bottleneck_after_ci_and_runtime_stabilize",
        },
    ]

    scored: list[dict[str, Any]] = []
    for item in lane_definitions:
        operational_gap = 100 - safe_number(item["base_signal"], default=0)
        priority_score = clamp(
            (item["impact"] * 0.30)
            + (operational_gap * 0.25)
            + (item["autonomy_gain"] * 0.20)
            + (item["cost_reduction"] * 0.15)
            - risk_penalty(item["risk"]) * 0.10
        )
        normalized_risk = risk_level(safe_number(item["base_signal"], default=0))
        if normalize_status(item["risk"]) in {"high", "critical", "failed", "blocked"}:
            normalized_risk = "high"
        scored.append(
            {
                "lane": item["lane"],
                "priority_score": round(priority_score, 2),
                "base_signal": safe_number(item["base_signal"], default=0),
                "impact_weight": item["impact"],
                "autonomy_gain": item["autonomy_gain"],
                "cost_reduction": item["cost_reduction"],
                "risk": normalized_risk,
                "action": action_for_priority(priority_score, normalized_risk),
                "reason": item["reason"],
            }
        )

    return sorted(scored, key=lambda entry: entry["priority_score"], reverse=True)


def build_strategic_governance_index(
    runtime_index: dict[str, Any],
    repo: str | None = None,
) -> dict[str, Any]:
    repo_name = repo or runtime_index.get("repo") or "unknown"
    lanes = build_lane_scores(runtime_index)
    next_bottleneck = classify_next_bottleneck(runtime_index)
    top_lane = lanes[0] if lanes else {}
    executive_score = safe_number((runtime_index.get("summary") or {}).get("executive_score"), default=0)
    confidence = normalize_status((runtime_index.get("summary") or {}).get("confidence"), "low")

    return {
        "schema_version": "1.0.0",
        "repo": repo_name,
        "generated_at_epoch": int(time.time()),
        "summary": {
            "status": "action_required" if top_lane.get("risk") == "high" else "governed",
            "strategic_score": round(sum(item["priority_score"] for item in lanes) / len(lanes), 2) if lanes else 0,
            "runtime_executive_score": executive_score,
            "confidence": confidence,
            "top_priority_lane": top_lane.get("lane", "unknown"),
            "recommended_action": top_lane.get("action", "unknown"),
            "next_bottleneck": next_bottleneck["name"],
        },
        "priority_lanes": lanes,
        "next_bottleneck": next_bottleneck,
        "decision_rules": {
            "execute_now_threshold": 80,
            "next_batch_threshold": 60,
            "backlog_threshold": 40,
            "risk_blocks_expansion": True,
            "source": "runtime_executive_index",
        },
        "links": {
            "runtime_executive_index": "docs/ops-dashboard/data/runtime-executive-index.json",
            "strategic_governance_index": "docs/ops-dashboard/data/strategic-governance-index.json",
            "ops_dashboard": "docs/ops-dashboard/index.html",
            "actions": f"https://github.com/{repo_name}/actions" if repo_name != "unknown" else "",
            "pulls": f"https://github.com/{repo_name}/pulls" if repo_name != "unknown" else "",
        },
        "guardrails": [
            "offline_static_generation",
            "report_only_contract",
            "no_runtime_github_api_call",
            "priority_does_not_override_required_ci",
            "high_risk_blocks_parallel_expansion",
            "evidence_first_before_autonomous_execution",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strategic governance prioritization index")
    parser.add_argument("--runtime-index", default="docs/ops-dashboard/data/runtime-executive-index.json")
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/strategic-governance-index.json")
    args = parser.parse_args()

    payload = build_strategic_governance_index(
        load_json(args.runtime_index),
        args.repo or None,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
