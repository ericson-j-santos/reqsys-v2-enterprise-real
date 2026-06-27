#!/usr/bin/env python3
"""Generate static operations dashboard data.

Entrada principal: artifact/relatorio do Repository Health Watchdog.
Saida: JSON estatico consumido por docs/ops-dashboard/index.html.

Este script e deterministico e nao acessa rede.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


def _load_watchdog_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "overall_status": "unknown",
            "critical_failure_count": None,
            "warning_count": None,
            "results": [],
            "source_missing": True,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _score(report: dict[str, Any]) -> int:
    status = report.get("overall_status")
    critical = int(report.get("critical_failure_count") or 0)
    warnings = int(report.get("warning_count") or 0)
    if status == "passed":
        return 100
    if status == "warning":
        return max(60, 90 - warnings * 10)
    if status == "failed":
        return max(0, 50 - critical * 25 - warnings * 5)
    return 40


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: list[float], fallback: float = 0.0) -> float:
    normalized = [float(value) for value in values if value is not None]
    if not normalized:
        return fallback
    return sum(normalized) / len(normalized)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _status_score(status: str | None) -> float:
    normalized = str(status or "").lower()
    if normalized == "passed":
        return 92.0
    if normalized in {"warning", "partial"}:
        return 78.0
    if normalized in {"failed", "critical"}:
        return 52.0
    return 62.0


def _default_projection_baseline() -> dict[str, Any]:
    return {
        "reference_time_brt": "",
        "observed_velocity": {
            "safe_parallel_increments": {"min": 2, "max": 4},
            "lead_time_minutes": {"min": 30, "max": 120},
            "ci_stabilization_percent": 75,
        },
        "real_completion": {
            "implemented_code_percent": 70,
            "validated_code_percent": 60,
            "consolidated_operational_evidence_percent": 55,
            "consolidated_enterprise_governance_percent": 60,
            "synchronized_environments_percent": 55,
            "navigable_analytical_runtime_percent": 60,
            "operational_autonomy_percent": 50,
            "total_gold_standard_percent": 50,
        },
        "remaining_gap": {
            "runtime_consolidation_percent": 20,
            "automated_evidence_percent": 25,
            "autonomous_operation_percent": 30,
            "analytics_drilldown_percent": 25,
            "production_hardening_percent": 25,
            "environment_sync_percent": 35,
            "full_living_governance_percent": 20,
            "enterprise_operational_ux_percent": 20,
        },
        "timeline_days": {
            "conservative": {
                "mvp_operational_consolidated": [5, 9],
                "synchronized_environments": [7, 12],
                "robust_operational_runtime": [8, 14],
                "technical_gold_standard": [14, 24],
                "total_gold_standard_consolidation": [21, 36],
            },
            "accelerated": {
                "robust_mvp": [3, 6],
                "strong_usable_production": [6, 10],
                "almost_full_environment_sync": [5, 9],
                "technical_gold_standard": [10, 18],
                "full_enterprise_consolidation": [14, 26],
            },
        },
        "main_bottlenecks": [],
        "risk_index": {},
        "trend": {},
        "probability_forecast": {},
        "accelerators": [],
    }


def _merge_projection_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    merged = _default_projection_baseline()
    for key, value in baseline.items():
        if key in {"observed_velocity", "real_completion", "remaining_gap", "timeline_days"} and isinstance(value, dict):
            merged[key] = {**merged.get(key, {}), **value}
            continue
        merged[key] = value
    return merged


def _scale_days_range(days_range: list[Any], pace_factor: float) -> list[int]:
    if not isinstance(days_range, list) or len(days_range) != 2:
        return [1, 1]
    start = int(float(days_range[0]))
    end = int(float(days_range[1]))
    effective = _clamp(pace_factor, 0.5, 1.4)
    low = max(1, int(round(start / effective)))
    high = max(low, int(round(end / effective)))
    return [low, high]


def _top_gap_priorities(remaining_gap: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for area, value in remaining_gap.items():
        try:
            gap = float(value)
        except (TypeError, ValueError):
            continue
        rows.append({"area": area, "gap_percent": round(gap, 2)})
    return sorted(rows, key=lambda row: row["gap_percent"], reverse=True)[:limit]


def _build_completion_projection(
    report: dict[str, Any],
    runtime_report: dict[str, Any],
    baseline_raw: dict[str, Any],
) -> dict[str, Any]:
    baseline = _merge_projection_baseline(baseline_raw or {})
    velocity = baseline.get("observed_velocity", {})
    completion = baseline.get("real_completion", {})
    remaining_gap = baseline.get("remaining_gap", {})
    runtime_maturity = float(runtime_report.get("maturity_percent") or _mean([
        float(item.get("maturity_percent")) for item in baseline.get("consolidated_state", []) if isinstance(item, dict)
    ], fallback=0.0))
    ci_status_signal = _status_score(report.get("overall_status"))
    ci_domain = ((runtime_report.get("domains") or {}).get("ci_cd") or {})
    ci_runtime_signal = float(ci_domain.get("score") or ci_status_signal)
    health_score = float(_score(report))
    baseline_ci = float(velocity.get("ci_stabilization_percent") or 75.0)
    ci_stability_signal = round(_mean([ci_status_signal, ci_runtime_signal, baseline_ci], fallback=baseline_ci), 2)
    safe_parallel = velocity.get("safe_parallel_increments") or {}
    parallel_avg = _mean([safe_parallel.get("min"), safe_parallel.get("max")], fallback=3.0)
    lead = velocity.get("lead_time_minutes") or {}
    lead_avg = _mean([lead.get("min"), lead.get("max")], fallback=60.0)
    lead_speed_signal = _clamp(90.0 / max(lead_avg, 1.0), 0.7, 1.2)
    pace_factor = _clamp(
        (
            (health_score / 100.0) * 0.34
            + (runtime_maturity / 100.0) * 0.30
            + (ci_stability_signal / 100.0) * 0.22
            + (_clamp(parallel_avg / 5.0, 0.2, 1.0) * 0.14)
        ) * lead_speed_signal,
        0.65,
        1.18,
    )
    baseline_total = float(completion.get("total_gold_standard_percent") or 50.0)
    blended_runtime = (runtime_maturity * 0.6) + (health_score * 0.4)
    current_completion = round(_clamp((baseline_total * 0.55) + (blended_runtime * 0.45), 0.0, 100.0), 1)
    scenario_timelines = baseline.get("timeline_days", {})
    conservative = scenario_timelines.get("conservative", {})
    accelerated = scenario_timelines.get("accelerated", {})
    accelerated_factor = _clamp(pace_factor * 1.22, 0.7, 1.4)
    conservative_ranges = {
        milestone: _scale_days_range(days_range, pace_factor)
        for milestone, days_range in conservative.items()
    }
    accelerated_ranges = {
        milestone: _scale_days_range(days_range, accelerated_factor)
        for milestone, days_range in accelerated.items()
    }

    return {
        "reference_time_brt": baseline.get("reference_time_brt", ""),
        "current_completion_percent": current_completion,
        "remaining_to_100_percent": round(max(0.0, 100.0 - current_completion), 1),
        "confidence_level": runtime_report.get("confidence_level", "medium"),
        "velocity_profile": {
            "pace_factor": round(pace_factor, 3),
            "ci_stability_signal_percent": ci_stability_signal,
            "safe_parallel_increments_average": round(parallel_avg, 2),
            "lead_time_minutes_average": round(lead_avg, 1),
        },
        "real_completion_breakdown": completion,
        "remaining_gap": remaining_gap,
        "priority_gaps": _top_gap_priorities(remaining_gap),
        "main_bottlenecks": baseline.get("main_bottlenecks", []),
        "risk_index": baseline.get("risk_index", {}),
        "trend": baseline.get("trend", {}),
        "probability_forecast": baseline.get("probability_forecast", {}),
        "accelerators": baseline.get("accelerators", []),
        "scenarios": {
            "conservative": conservative_ranges,
            "accelerated": accelerated_ranges,
        },
    }


def _runtime_depth(runtime_report: dict[str, Any]) -> dict[str, Any]:
    depth = runtime_report.get("gold_standard_depth") or {}
    axes = depth.get("axes") or {}
    return {
        "available": bool(depth),
        "strategy": depth.get("strategy", ""),
        "overall_status": depth.get("overall_status", "unknown"),
        "overall_score": depth.get("overall_score"),
        "focus_order": depth.get("operational_focus_order", []),
        "axes": [
            {
                "id": axis_id,
                "status": axis.get("status"),
                "score": axis.get("score"),
                "operator_action": axis.get("operator_action"),
            }
            for axis_id, axis in axes.items()
        ],
    }


def _severity_from_status(status: Any) -> str:
    normalized = str(status or "unknown").lower()
    if normalized in {"failed", "failure", "critical", "unhealthy", "high"}:
        return "critical"
    if normalized in {"warning", "warn", "medium", "degraded"}:
        return "warning"
    if normalized in {"partial", "pending", "unknown", "missing"}:
        return "info"
    return "normal"


def _domain_drilldowns(runtime_report: dict[str, Any]) -> list[dict[str, Any]]:
    domains = runtime_report.get("domains") or {}
    environment_drift = runtime_report.get("environment_drift") or {}
    risk = runtime_report.get("runtime_risk_scoring") or {}
    rows: list[dict[str, Any]] = []
    for domain_id, domain in domains.items():
        signals = domain.get("signals") or []
        domain_findings = environment_drift.get("findings") if domain_id == "environment" else []
        rows.append({
            "id": domain_id,
            "status": domain.get("status", "unknown"),
            "severity": _severity_from_status(domain.get("status")),
            "score": domain.get("score"),
            "signals_available": domain.get("signals_available", 0),
            "signals_total": domain.get("signals_total", 0),
            "health": {
                "maturity_percent": runtime_report.get("maturity_percent"),
                "confidence_level": runtime_report.get("confidence_level"),
                "operational_risk": runtime_report.get("operational_risk"),
            },
            "evidence": [signal for signal in signals if signal.get("available")],
            "missing_evidence": [signal for signal in signals if not signal.get("available")],
            "risk": risk if domain_id == "runtime_risk" else {"status": domain.get("status"), "severity": _severity_from_status(domain.get("status"))},
            "environment_drift": environment_drift if domain_id == "environment" else {"findings": domain_findings},
            "governance": {
                "guardrails": runtime_report.get("guardrails", []),
                "next_required_actions": runtime_report.get("next_required_actions", []),
                "gold_standard_status": runtime_report.get("gold_standard_status", {}),
            } if domain_id == "governance" else {},
        })
    return rows


def _extract_pr(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    match = re.search(r"#(\d+)|pull/(\d+)|PR[-_ ]?(\d+)", text, re.IGNORECASE)
    if not match:
        return ""
    return next(group for group in match.groups() if group)


def _incident_timeline(report: dict[str, Any], runtime_report: dict[str, Any], evidence_graph: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for check in report.get("results", []) or []:
        events.append({
            "source": "repository_health_watchdog",
            "title": check.get("name", "check operacional"),
            "domain": check.get("domain") or check.get("category") or "ci_cd",
            "workflow": check.get("workflow") or check.get("name", ""),
            "pr": _extract_pr(check),
            "status": check.get("status", "unknown"),
            "severity": check.get("severity") or _severity_from_status(check.get("status")),
            "evidence": check.get("evidence", {}),
        })
    for domain_id, domain in (runtime_report.get("domains") or {}).items():
        events.append({
            "source": "runtime_health_report",
            "title": f"Domínio {domain_id}",
            "domain": domain_id,
            "workflow": "runtime-health-center",
            "pr": "",
            "status": domain.get("status", "unknown"),
            "severity": _severity_from_status(domain.get("status")),
            "evidence": {"score": domain.get("score"), "signals_available": domain.get("signals_available"), "signals_total": domain.get("signals_total")},
        })
    for artifact in ((runtime_report.get("ingested_artifacts") or {}).get("artifacts") or []):
        events.append({
            "source": "runtime_artifact_catalog",
            "title": artifact.get("id", "artifact"),
            "domain": "evidence_gate",
            "workflow": artifact.get("id", ""),
            "pr": _extract_pr(artifact),
            "status": artifact.get("status", "unknown"),
            "severity": _severity_from_status(artifact.get("status")),
            "evidence": artifact,
        })
    graph_items = []
    for key in ("events", "nodes", "edges"):
        value = evidence_graph.get(key)
        if isinstance(value, list):
            graph_items.extend(value)
    for item in graph_items:
        if not isinstance(item, dict):
            continue
        events.append({
            "source": "runtime_operational_evidence_graph",
            "title": item.get("title") or item.get("id") or item.get("name") or "evidência correlacionada",
            "domain": item.get("domain") or item.get("type") or "evidence_gate",
            "workflow": item.get("workflow") or item.get("workflow_name") or "",
            "pr": str(item.get("pr") or item.get("pull_request") or _extract_pr(item)),
            "status": item.get("status", "unknown"),
            "severity": item.get("severity") or _severity_from_status(item.get("status")),
            "evidence": item,
        })
    return events


def _public_runtime_summary(public_runtime: dict[str, Any]) -> dict[str, Any]:
    readiness = public_runtime.get("readiness") or {}
    return {
        "available": bool(public_runtime),
        "environment": readiness.get("environment") or public_runtime.get("environment") or "prod",
        "base_url": public_runtime.get("base_url", ""),
        "operational_status": readiness.get("operational_status", "unknown"),
        "readiness_percent": readiness.get("readiness_percent"),
        "response_time": readiness.get("response_time"),
        "dashboard_ready": readiness.get("dashboard_ready", False),
        "login_ready": readiness.get("login_ready", False),
        "api_ready": readiness.get("api_ready", False),
        "runtime_ready": readiness.get("runtime_ready", False),
        "evidence_ready": readiness.get("evidence_ready", False),
        "blocking_issues": readiness.get("blocking_issues", []),
        "checks": public_runtime.get("checks", {}),
    }


def build_dashboard_payload(
    report: dict[str, Any],
    repo: str,
    runtime_report: dict[str, Any] | None = None,
    evidence_graph: dict[str, Any] | None = None,
    public_runtime: dict[str, Any] | None = None,
    projection_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    results = report.get("results", []) or []
    runtime_report = runtime_report or {}
    evidence_graph = evidence_graph or {}
    public_runtime = public_runtime or {}
    return {
        "schema_version": "1.1.0",
        "repo": repo or report.get("repo") or "unknown",
        "generated_at_epoch": int(time.time()),
        "overall_status": report.get("overall_status", "unknown"),
        "health_score": _score(report),
        "critical_failure_count": report.get("critical_failure_count"),
        "warning_count": report.get("warning_count"),
        "source_missing": report.get("source_missing", False),
        "checks": results,
        "links": {
            "actions": f"https://github.com/{repo}/actions" if repo else "",
            "pulls": f"https://github.com/{repo}/pulls" if repo else "",
            "main": f"https://github.com/{repo}/tree/main" if repo else "",
        },
        "public_runtime_readiness": _public_runtime_summary(public_runtime),
        "runtime_gold_standard_depth": _runtime_depth(runtime_report),
        "runtime_domain_drilldowns": _domain_drilldowns(runtime_report),
        "incident_timeline": _incident_timeline(report, runtime_report, evidence_graph),
        "runtime_sources": {
            "runtime_health_report_available": bool(runtime_report),
            "runtime_operational_evidence_graph_available": bool(evidence_graph),
            "public_runtime_validation_available": bool(public_runtime),
        },
        "completion_projection": _build_completion_projection(report, runtime_report, projection_baseline or {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys ops dashboard data")
    parser.add_argument("--watchdog-report", default="artifacts/repository-health-watchdog/repository-health-report.json")
    parser.add_argument("--repo", default="")
    parser.add_argument("--output", default="docs/ops-dashboard/data/health.json")
    parser.add_argument("--runtime-health-report", default="artifacts/runtime-health-center/runtime-health-report.json")
    parser.add_argument("--evidence-graph", default="artifacts/runtime-operational-evidence-graph/runtime-operational-evidence-graph.json")
    parser.add_argument("--public-runtime-validation", default="artifacts/runtime/public-runtime-validation.json")
    parser.add_argument("--projection-baseline", default="config/completion-projection-baseline.json")
    args = parser.parse_args()

    report = _load_watchdog_report(Path(args.watchdog_report))
    runtime_report = _load_optional_json(Path(args.runtime_health_report))
    evidence_graph = _load_optional_json(Path(args.evidence_graph))
    public_runtime = _load_optional_json(Path(args.public_runtime_validation))
    projection_baseline = _load_optional_json(Path(args.projection_baseline))
    payload = build_dashboard_payload(
        report,
        args.repo,
        runtime_report,
        evidence_graph,
        public_runtime,
        projection_baseline,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
