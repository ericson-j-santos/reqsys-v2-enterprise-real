#!/usr/bin/env python3
"""Build an automatically instrumented ReqSys executive readiness contract."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def number(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            continue
    return None


def weighted(values: list[tuple[float | None, int]]) -> float | None:
    available = [(value, weight) for value, weight in values if value is not None]
    if not available:
        return None
    return round(sum(value * weight for value, weight in available) / sum(weight for _, weight in available), 2)


def ci_success_rate(payload: dict[str, Any]) -> float | None:
    summary = payload.get("summary") or payload.get("metrics") or {}
    return number(
        payload.get("success_rate_percent"),
        payload.get("success_rate"),
        summary.get("success_rate_percent"),
        summary.get("success_rate"),
    )


def build_contract(
    readiness: dict[str, Any], runtime: dict[str, Any], merge: dict[str, Any], ci: dict[str, Any]
) -> dict[str, Any]:
    merge_data = merge.get("merge_intelligence") or {}
    trend = merge.get("trend") or {}
    domains = runtime.get("domains") or {}
    gold = runtime.get("gold_standard_operational_risk") or {}

    consumer_readiness = number(readiness.get("readiness_percent"))
    runtime_score = number(runtime.get("validation_score"))
    production_score = number(gold.get("overall_score"))
    confidence = number(runtime.get("confidence_percent"))
    runtime_risk = number(runtime.get("operational_risk_percent"))
    public_readiness = number((domains.get("public_readiness") or {}).get("score"))
    mergeability = number(merge_data.get("mergeability_score"))
    queue_pressure = number(merge_data.get("queue_pressure"))
    ci_stability = ci_success_rate(ci)
    active_lanes = len(trend.get("parallel_lanes_active") or [])
    lane_capacity = min(100.0, active_lanes / 4 * 100)
    queue_headroom = None if queue_pressure is None else 100 - queue_pressure
    throughput_score = weighted([(mergeability, 45), (queue_headroom, 35), (lane_capacity, 20)])

    operational_readiness = weighted(
        [(consumer_readiness, 20), (runtime_score, 35), (production_score, 25), (ci_stability, 20)]
    )
    technical_progress = weighted([(consumer_readiness, 35), (runtime_score, 40), (mergeability, 25)])
    governance = weighted([(consumer_readiness, 55), (mergeability, 25), (number(gold.get("source_coverage_percent")), 20)])

    required_metrics = {
        "consumer_readiness_percent": consumer_readiness,
        "runtime_validation_percent": runtime_score,
        "production_readiness_percent": production_score,
        "ci_stability_percent": ci_stability,
        "mergeability_percent": mergeability,
        "throughput_parallel_percent": throughput_score,
    }
    coverage = round(sum(value is not None for value in required_metrics.values()) / len(required_metrics) * 100, 2)
    risk = runtime_risk if runtime_risk is not None else (None if operational_readiness is None else round(100 - operational_readiness, 2))

    if operational_readiness is None:
        status = "INSUFFICIENT_EVIDENCE"
    elif operational_readiness >= 95 and runtime.get("production_ready") is True:
        status = "READY"
    elif operational_readiness >= 75:
        status = "CONSOLIDATING"
    else:
        status = "EVIDENCE_INCOMPLETE"

    throughput_class = "unknown"
    if throughput_score is not None:
        throughput_class = "high" if throughput_score >= 80 else "medium" if throughput_score >= 60 else "low"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-instrumented-executive-readiness",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report_only",
        "production_blocker": False,
        "automatic_promotion_allowed": False,
        "status": status,
        "metric_coverage_percent": coverage,
        "operational_readiness_percent": operational_readiness,
        "indicators": {
            "technical_progress_percent": technical_progress,
            "operational_progress_percent": runtime_score,
            "user_final_percent": public_readiness,
            "governance_percent": governance,
            "production_percent": production_score,
            "confidence_percent": confidence,
            "operational_risk_percent": risk,
            "ci_stability_percent": ci_stability,
            "throughput_parallel_percent": throughput_score,
            "throughput_parallel_class": throughput_class,
            "active_parallel_lanes": active_lanes,
            "queue_pressure_percent": queue_pressure,
            "mergeability_percent": mergeability,
        },
        "milestones": {
            "mvp": "achieved" if technical_progress is not None and technical_progress >= 90 else "in_progress",
            "production": "ready" if status == "READY" else "blocked_by_evidence",
            "gold_standard": "achieved" if production_score is not None and production_score >= 95 else "in_progress",
            "eta_calendar": None,
            "eta_reason": "insufficient_instrumented_history" if not ci else "derived_from_current_snapshot_only",
        },
        "sources": {
            "consumer_readiness": bool(readiness),
            "runtime_validation": bool(runtime),
            "merge_intelligence": bool(merge),
            "ci_lead_time": bool(ci),
        },
        "metric_provenance": {
            "consumer_readiness_percent": "reqsys-single-state-consumer-readiness.report.readiness_percent",
            "runtime_validation_percent": "runtime-validation-snapshot.validation_score",
            "production_readiness_percent": "runtime-validation-snapshot.gold_standard_operational_risk.overall_score",
            "ci_stability_percent": "ci-lead-time-analytics.success_rate_percent",
            "throughput_parallel_percent": "weighted(mergeability, queue_headroom, active_parallel_lanes)",
        },
        "next_safe_increment": (
            "collect_ci_lead_time_artifact" if ci_stability is None else "publish_instrumented_summary_to_single_state"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--merge", type=Path, required=True)
    parser.add_argument("--ci", type=Path, default=Path("artifacts/ci-lead-time-analytics/ci-lead-time-analytics.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = build_contract(
        load_optional(args.readiness), load_optional(args.runtime), load_optional(args.merge), load_optional(args.ci)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": contract["status"], "coverage": contract["metric_coverage_percent"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
