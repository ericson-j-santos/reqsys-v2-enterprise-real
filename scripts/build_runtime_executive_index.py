#!/usr/bin/env python3
"""Build consolidated runtime executive index for public dashboard consumption.

The builder is deterministic, offline and safe for CI. It aggregates existing
static artifacts into a single executive contract that can be consumed by the
public dashboard/Fly.io without calling GitHub APIs at runtime.
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


def status_to_risk(status: Any) -> str:
    normalized = normalize_status(status)
    if normalized in {
        "passed",
        "success",
        "healthy",
        "stable",
        "low",
        "merge_imediato",
        "true",
        "ok",
        "ready_for_production",
        "ready",
    }:
        return "low"
    if normalized in {
        "failed",
        "failure",
        "critical",
        "high",
        "blocked",
        "isolamento_obrigatorio",
        "false",
        "blocked_for_production",
        "not_ready",
    }:
        return "high"
    return "medium"


def worst_risk(*risks: Any) -> str:
    normalized = [normalize_status(risk) for risk in risks if risk is not None]
    if any(risk == "high" for risk in normalized):
        return "high"
    if any(risk == "medium" for risk in normalized):
        return "medium"
    return "low" if normalized else "medium"


def summarize_health(health: dict[str, Any]) -> dict[str, Any]:
    status = normalize_status(health.get("overall_status"))
    return {
        "status": status,
        "score": safe_number(health.get("health_score"), default=0),
        "critical_failure_count": health.get("critical_failure_count"),
        "warning_count": health.get("warning_count"),
        "source_missing": bool(health.get("source_missing")),
        "risk": status_to_risk(status),
    }


def summarize_readiness(health: dict[str, Any]) -> dict[str, Any]:
    readiness = health.get("public_runtime_readiness") or {}
    status = normalize_status(readiness.get("operational_status"))
    readiness_percent = safe_number(readiness.get("readiness_percent"), default=0)
    blocking_issues = readiness.get("blocking_issues") or []
    return {
        "available": bool(readiness.get("available")),
        "status": status,
        "readiness_percent": readiness_percent,
        "base_url": readiness.get("base_url") or "",
        "response_time": readiness.get("response_time"),
        "dashboard_ready": bool(readiness.get("dashboard_ready")),
        "login_ready": bool(readiness.get("login_ready")),
        "api_ready": bool(readiness.get("api_ready")),
        "runtime_ready": bool(readiness.get("runtime_ready")),
        "evidence_ready": bool(readiness.get("evidence_ready")),
        "blocking_issue_count": len(blocking_issues),
        "risk": "high" if blocking_issues else status_to_risk(status),
    }


def summarize_merge_intelligence(
    merge_index: dict[str, Any],
    lane_priority: dict[str, Any],
    conflict_risk_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conflict_risk_report = conflict_risk_report or {}
    intelligence = merge_index.get("merge_intelligence") or {}
    ranking = lane_priority.get("ranking") or merge_index.get("lane_priority", {}).get("ranking") or []
    risk = normalize_status(conflict_risk_report.get("risk"), normalize_status(intelligence.get("risk")))
    lane = normalize_status(conflict_risk_report.get("lane"), normalize_status(intelligence.get("lane")))
    parallel_safe = bool(conflict_risk_report.get("parallel_safe", intelligence.get("parallel_safe", False)))
    recommendation = normalize_status(
        conflict_risk_report.get("recommendation"),
        normalize_status(intelligence.get("recommendation"), "aguardar_estabilizacao"),
    )
    queue_saturation = normalize_status(intelligence.get("queue_saturation"), "unknown")
    blocking_reasons = conflict_risk_report.get("blocking_reasons") or intelligence.get("blocking_reasons") or []
    critical_files = conflict_risk_report.get("critical_files") or []
    available = bool(conflict_risk_report) or (bool(merge_index) and bool(merge_index.get("source_available", True)))
    score = safe_number(intelligence.get("mergeability_score"), default=0)
    if conflict_risk_report and not intelligence.get("mergeability_score"):
        score = 92 if risk == "low" and parallel_safe else 75 if risk in {"medium", "high"} else 30

    return {
        "available": available,
        "risk": risk,
        "lane": lane,
        "parallel_safe": parallel_safe,
        "mergeability_score": score,
        "recommendation": recommendation,
        "queue_saturation": queue_saturation,
        "queue_pressure": safe_number(intelligence.get("queue_pressure"), default=0),
        "confidence": normalize_status(intelligence.get("confidence"), "medium" if conflict_risk_report else "low"),
        "blocking_reasons": blocking_reasons,
        "critical_file_count": len(critical_files),
        "hotspot_count": len(merge_index.get("hotspot_heatmap") or []),
        "safe_lane_count": sum(1 for item in ranking if normalize_status(item.get("parallelism")) == "safe"),
        "risk_level": status_to_risk(recommendation if blocking_reasons else risk or queue_saturation),
        "source_artifacts": {
            "merge_intelligence_index": bool(merge_index),
            "lane_priority": bool(lane_priority),
            "conflict_risk_report": bool(conflict_risk_report),
        },
    }


def summarize_finalization(health: dict[str, Any], finalization_report: dict[str, Any] | None = None) -> dict[str, Any]:
    finalization_report = finalization_report or {}
    finalization = finalization_report or health.get("delivery_finalization") or {}
    status = normalize_status(finalization.get("status") or finalization.get("overall_status"))
    indicators = finalization.get("indicators") or finalization.get("checks") or []
    passed_indicators = [
        item for item in indicators
        if normalize_status(item.get("status")) in {"passed", "success", "ok", "healthy"}
    ]
    indicator_count = int(finalization.get("indicator_count") or len(indicators) or 0)
    passed_indicator_count = int(finalization.get("passed_indicator_count") or len(passed_indicators) or 0)
    return {
        "available": bool(finalization_report) or bool(finalization.get("available")),
        "status": status,
        "final_score": safe_number(
            finalization.get("final_score"),
            finalization.get("score"),
            finalization.get("finalization_percent"),
            default=0,
        ),
        "residual_gap": safe_number(finalization.get("residual_gap"), finalization.get("remaining_gap_pp"), default=0),
        "indicator_count": indicator_count,
        "passed_indicator_count": passed_indicator_count,
        "risk": status_to_risk(status),
        "source_artifact": "delivery-finalization-report" if finalization_report else "health.delivery_finalization",
    }


def summarize_evidence_gate(health: dict[str, Any], evidence_gate_report: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence_gate_report = evidence_gate_report or {}
    if evidence_gate_report:
        gate = evidence_gate_report.get("gate") or evidence_gate_report
        status = normalize_status(gate.get("status"))
        failures = gate.get("failures") or []
        required = gate.get("required_workflows") or []
        passed_count = sum(1 for item in required if int(item.get("successful_runs") or 0) > 0)
        failed_count = len(failures)
        return {
            "available": True,
            "status": status,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "required_workflow_count": len(required),
            "observed_artifact_count": len(gate.get("observed_artifacts") or []),
            "risk": "high" if failed_count else status_to_risk(status),
            "source_artifact": "pr-evidence-gate",
        }

    checks = health.get("checks") or []
    gate_checks = [
        item for item in checks
        if "evidence" in normalize_status(item.get("name"))
        or "evidence" in normalize_status(item.get("workflow"))
        or "evidence_gate" in normalize_status(item.get("domain"))
    ]
    if not gate_checks:
        return {
            "available": False,
            "status": "unknown",
            "passed_count": 0,
            "failed_count": 0,
            "risk": "medium",
            "source_artifact": "fallback",
        }
    failed = [item for item in gate_checks if status_to_risk(item.get("status")) == "high"]
    passed = [item for item in gate_checks if normalize_status(item.get("status")) in {"passed", "success"}]
    return {
        "available": True,
        "status": "failed" if failed else "passed" if len(passed) == len(gate_checks) else "warning",
        "passed_count": len(passed),
        "failed_count": len(failed),
        "risk": "high" if failed else "low" if len(passed) == len(gate_checks) else "medium",
        "source_artifact": "health.checks",
    }


def summarize_runtime_validation(validation: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validation or {}
    if not validation:
        return {
            "available": False,
            "status": "unknown",
            "validation_score": 0,
            "operational_risk_percent": 100,
            "gold_standard_score": 0,
            "public_runtime_ready": False,
            "post_merge_ready": False,
            "production_ready": False,
            "risk": "medium",
            "source_artifact": "runtime-validation-snapshot",
        }
    state = normalize_status(validation.get("overall_state"))
    risk_percent = int(validation.get("operational_risk_percent") or 0)
    gold = (validation.get("gold_standard_operational_risk") or {}).get("overall_score") or 0
    return {
        "available": True,
        "status": state,
        "validation_score": int(validation.get("validation_score") or 0),
        "operational_risk_percent": risk_percent,
        "gold_standard_score": int(gold),
        "public_runtime_ready": bool(validation.get("public_runtime_ready")),
        "post_merge_ready": bool(validation.get("post_merge_ready")),
        "production_ready": bool(validation.get("production_ready")),
        "risk": "low" if risk_percent <= 15 else "medium" if risk_percent <= 35 else "high",
        "source_artifact": "runtime-validation-snapshot",
    }


def summarize_executive_readiness(readiness_gate: dict[str, Any] | None = None) -> dict[str, Any]:
    readiness_gate = readiness_gate or {}
    readiness = readiness_gate.get("executive_readiness") or {}
    if not readiness_gate:
        return {
            "available": False,
            "status": "unknown",
            "decision": "UNKNOWN",
            "ready_for_production": False,
            "score": 0,
            "risk_percent": 100,
            "blocker_count": 0,
            "blockers": [],
            "risk": "medium",
            "source_artifact": "executive-readiness-gate",
        }

    decision = normalize_status(readiness.get("decision"), "unknown").upper()
    ready = bool(readiness.get("ready_for_production"))
    score = safe_number(readiness.get("score"), default=0)
    risk_percent = safe_number(readiness.get("risk_percent"), default=max(0, 100 - int(score)))
    blockers = readiness.get("blockers") or []
    status = normalize_status(readiness.get("overall_state"), "passed" if ready else "blocked")
    risk = "high" if blockers or not ready else "low" if risk_percent <= 15 else "medium"
    domains = readiness_gate.get("domains") or {}

    return {
        "available": True,
        "status": status,
        "decision": decision,
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
        "risk": risk,
        "source_artifact": "executive-readiness-gate",
    }


def build_runtime_executive_index(
    health: dict[str, Any],
    merge_index: dict[str, Any] | None = None,
    lane_priority: dict[str, Any] | None = None,
    repo: str | None = None,
    evidence_gate_report: dict[str, Any] | None = None,
    finalization_report: dict[str, Any] | None = None,
    conflict_risk_report: dict[str, Any] | None = None,
    runtime_validation: dict[str, Any] | None = None,
    executive_readiness_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merge_index = merge_index or {}
    lane_priority = lane_priority or {}
    repo_name = repo or health.get("repo") or merge_index.get("repo") or "unknown"

    health_summary = summarize_health(health)
    readiness_summary = summarize_readiness(health)
    merge_summary = summarize_merge_intelligence(merge_index, lane_priority, conflict_risk_report)
    evidence_summary = summarize_evidence_gate(health, evidence_gate_report)
    finalization_summary = summarize_finalization(health, finalization_report)
    validation_summary = summarize_runtime_validation(runtime_validation)
    executive_readiness_summary = summarize_executive_readiness(executive_readiness_gate)

    consolidated_risk = worst_risk(
        health_summary["risk"],
        readiness_summary["risk"],
        merge_summary["risk_level"],
        evidence_summary["risk"],
        finalization_summary["risk"],
        validation_summary["risk"] if validation_summary["available"] else None,
        executive_readiness_summary["risk"] if executive_readiness_summary["available"] else None,
    )

    score_values = [
        safe_number(health_summary["score"], default=0),
        safe_number(readiness_summary["readiness_percent"], default=0),
        safe_number(merge_summary["mergeability_score"], default=0),
        100 if evidence_summary["risk"] == "low" else 60 if evidence_summary["risk"] == "medium" else 20,
        safe_number(finalization_summary["final_score"], default=0),
    ]
    if validation_summary["available"]:
        score_values.append(safe_number(validation_summary["validation_score"], default=0))
    if executive_readiness_summary["available"]:
        score_values.append(safe_number(executive_readiness_summary["score"], default=0))
    executive_score = round(sum(score_values) / len(score_values), 2)

    production_ready = bool(executive_readiness_summary.get("ready_for_production")) if executive_readiness_summary["available"] else bool(validation_summary.get("production_ready"))

    return {
        "schema_version": "1.2.0",
        "repo": repo_name,
        "generated_at_epoch": int(time.time()),
        "summary": {
            "status": "passed" if production_ready and consolidated_risk == "low" else "critical" if consolidated_risk == "high" else "warning",
            "executive_score": executive_score,
            "risk": consolidated_risk,
            "confidence": merge_summary.get("confidence", "low"),
            "production_ready": production_ready,
            "executive_readiness_decision": executive_readiness_summary.get("decision", "UNKNOWN"),
            "source": "static_offline_artifacts",
        },
        "cards": {
            "health": health_summary,
            "readiness": readiness_summary,
            "merge_intelligence": merge_summary,
            "evidence_gate": evidence_summary,
            "finalization": finalization_summary,
            "runtime_validation": validation_summary,
            "executive_readiness": executive_readiness_summary,
        },
        "links": {
            "ops_dashboard": "docs/ops-dashboard/index.html",
            "operational_evidence_hub": "docs/dashboard/operational-evidence-hub.html",
            "health_json": "docs/ops-dashboard/data/health.json",
            "merge_intelligence_index": "docs/ops-dashboard/data/merge-intelligence-index.json",
            "merge_lane_priority": "docs/ops-dashboard/data/merge-lane-priority.json",
            "runtime_executive_index": "docs/ops-dashboard/data/runtime-executive-index.json",
            "conflict_risk_report": "docs/ops-dashboard/data/conflict-risk-report.json",
            "pr_evidence_gate": "audit/pr-evidence-gate.json",
            "delivery_finalization_report": "artifacts/delivery-finalization/delivery-finalization-report.json",
            "runtime_validation_snapshot": "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
            "executive_readiness_gate": "artifacts/executive-readiness-gate/executive-readiness-gate.json",
            "executive_brief": "docs/ops-dashboard/data/executive-brief.json",
            "actions": f"https://github.com/{repo_name}/actions" if repo_name != "unknown" else "",
            "pulls": f"https://github.com/{repo_name}/pulls" if repo_name != "unknown" else "",
        },
        "guardrails": [
            "offline_static_generation",
            "no_runtime_github_api_call",
            "safe_fallback_when_source_artifact_missing",
            "report_only_contract_for_public_dashboard",
            "real_artifact_precedence_when_available",
            "executive_readiness_gate_precedence_for_production_decision",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build consolidated runtime executive index")
    parser.add_argument("--health", default="docs/ops-dashboard/data/health.json")
    parser.add_argument("--merge-intelligence", default="docs/ops-dashboard/data/merge-intelligence-index.json")
    parser.add_argument("--lane-priority", default="docs/ops-dashboard/data/merge-lane-priority.json")
    parser.add_argument("--evidence-gate", default="audit/pr-evidence-gate.json")
    parser.add_argument("--delivery-finalization", default="artifacts/delivery-finalization/delivery-finalization-report.json")
    parser.add_argument("--conflict-risk-report", default="docs/ops-dashboard/data/conflict-risk-report.json")
    parser.add_argument(
        "--runtime-validation",
        default="artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
    )
    parser.add_argument(
        "--executive-readiness",
        default="artifacts/executive-readiness-gate/executive-readiness-gate.json",
    )
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/runtime-executive-index.json")
    args = parser.parse_args()

    payload = build_runtime_executive_index(
        load_json(args.health),
        load_json(args.merge_intelligence),
        load_json(args.lane_priority),
        args.repo or None,
        load_json(args.evidence_gate),
        load_json(args.delivery_finalization),
        load_json(args.conflict_risk_report),
        load_json(args.runtime_validation),
        load_json(args.executive_readiness),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
