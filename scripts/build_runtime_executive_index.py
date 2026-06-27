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
    if normalized in {"passed", "success", "healthy", "stable", "low", "merge_imediato"}:
        return "low"
    if normalized in {"failed", "failure", "critical", "high", "blocked", "isolamento_obrigatorio"}:
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


def summarize_merge_intelligence(merge_index: dict[str, Any], lane_priority: dict[str, Any]) -> dict[str, Any]:
    intelligence = merge_index.get("merge_intelligence") or {}
    ranking = lane_priority.get("ranking") or merge_index.get("lane_priority", {}).get("ranking") or []
    recommendation = normalize_status(intelligence.get("recommendation"), "aguardar_estabilizacao")
    queue_saturation = normalize_status(intelligence.get("queue_saturation"), "unknown")
    blocking_reasons = intelligence.get("blocking_reasons") or []
    return {
        "available": bool(merge_index) and bool(merge_index.get("source_available", True)),
        "risk": normalize_status(intelligence.get("risk")),
        "lane": normalize_status(intelligence.get("lane")),
        "parallel_safe": bool(intelligence.get("parallel_safe")),
        "mergeability_score": safe_number(intelligence.get("mergeability_score"), default=0),
        "recommendation": recommendation,
        "queue_saturation": queue_saturation,
        "queue_pressure": safe_number(intelligence.get("queue_pressure"), default=0),
        "confidence": normalize_status(intelligence.get("confidence"), "low"),
        "blocking_reasons": blocking_reasons,
        "hotspot_count": len(merge_index.get("hotspot_heatmap") or []),
        "safe_lane_count": sum(1 for item in ranking if normalize_status(item.get("parallelism")) == "safe"),
        "risk_level": status_to_risk(recommendation if blocking_reasons else queue_saturation),
    }


def summarize_finalization(health: dict[str, Any]) -> dict[str, Any]:
    finalization = health.get("delivery_finalization") or {}
    status = normalize_status(finalization.get("status"))
    return {
        "available": bool(finalization.get("available")),
        "status": status,
        "final_score": safe_number(finalization.get("final_score"), default=0),
        "residual_gap": safe_number(finalization.get("residual_gap"), default=0),
        "indicator_count": int(finalization.get("indicator_count") or 0),
        "passed_indicator_count": int(finalization.get("passed_indicator_count") or 0),
        "risk": status_to_risk(status),
    }


def summarize_evidence_gate(health: dict[str, Any]) -> dict[str, Any]:
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
        }
    failed = [item for item in gate_checks if status_to_risk(item.get("status")) == "high"]
    passed = [item for item in gate_checks if normalize_status(item.get("status")) in {"passed", "success"}]
    return {
        "available": True,
        "status": "failed" if failed else "passed" if len(passed) == len(gate_checks) else "warning",
        "passed_count": len(passed),
        "failed_count": len(failed),
        "risk": "high" if failed else "low" if len(passed) == len(gate_checks) else "medium",
    }


def build_runtime_executive_index(
    health: dict[str, Any],
    merge_index: dict[str, Any] | None = None,
    lane_priority: dict[str, Any] | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    merge_index = merge_index or {}
    lane_priority = lane_priority or {}
    repo_name = repo or health.get("repo") or merge_index.get("repo") or "unknown"

    health_summary = summarize_health(health)
    readiness_summary = summarize_readiness(health)
    merge_summary = summarize_merge_intelligence(merge_index, lane_priority)
    evidence_summary = summarize_evidence_gate(health)
    finalization_summary = summarize_finalization(health)

    consolidated_risk = worst_risk(
        health_summary["risk"],
        readiness_summary["risk"],
        merge_summary["risk_level"],
        evidence_summary["risk"],
        finalization_summary["risk"],
    )

    score_values = [
        safe_number(health_summary["score"], default=0),
        safe_number(readiness_summary["readiness_percent"], default=0),
        safe_number(merge_summary["mergeability_score"], default=0),
        100 if evidence_summary["risk"] == "low" else 60 if evidence_summary["risk"] == "medium" else 20,
        safe_number(finalization_summary["final_score"], default=0),
    ]
    executive_score = round(sum(score_values) / len(score_values), 2)

    return {
        "schema_version": "1.0.0",
        "repo": repo_name,
        "generated_at_epoch": int(time.time()),
        "summary": {
            "status": "critical" if consolidated_risk == "high" else "warning" if consolidated_risk == "medium" else "passed",
            "executive_score": executive_score,
            "risk": consolidated_risk,
            "confidence": merge_summary.get("confidence", "low"),
            "source": "static_offline_artifacts",
        },
        "cards": {
            "health": health_summary,
            "readiness": readiness_summary,
            "merge_intelligence": merge_summary,
            "evidence_gate": evidence_summary,
            "finalization": finalization_summary,
        },
        "links": {
            "ops_dashboard": "docs/ops-dashboard/index.html",
            "operational_evidence_hub": "docs/dashboard/operational-evidence-hub.html",
            "health_json": "docs/ops-dashboard/data/health.json",
            "merge_intelligence_index": "docs/ops-dashboard/data/merge-intelligence-index.json",
            "merge_lane_priority": "docs/ops-dashboard/data/merge-lane-priority.json",
            "runtime_executive_index": "docs/ops-dashboard/data/runtime-executive-index.json",
            "actions": f"https://github.com/{repo_name}/actions" if repo_name != "unknown" else "",
            "pulls": f"https://github.com/{repo_name}/pulls" if repo_name != "unknown" else "",
        },
        "guardrails": [
            "offline_static_generation",
            "no_runtime_github_api_call",
            "safe_fallback_when_source_artifact_missing",
            "report_only_contract_for_public_dashboard",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build consolidated runtime executive index")
    parser.add_argument("--health", default="docs/ops-dashboard/data/health.json")
    parser.add_argument("--merge-intelligence", default="docs/ops-dashboard/data/merge-intelligence-index.json")
    parser.add_argument("--lane-priority", default="docs/ops-dashboard/data/merge-lane-priority.json")
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/runtime-executive-index.json")
    args = parser.parse_args()

    payload = build_runtime_executive_index(
        load_json(args.health),
        load_json(args.merge_intelligence),
        load_json(args.lane_priority),
        args.repo or None,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
