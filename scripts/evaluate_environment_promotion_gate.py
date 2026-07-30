#!/usr/bin/env python3
"""Evaluate governed promotion readiness for DEV, STG and PROD."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLICY = {
    "dev": {"minimum_readiness": 70.0, "minimum_coverage": 80.0, "blocking": False},
    "stg": {"minimum_readiness": 85.0, "minimum_coverage": 90.0, "blocking": False},
    "prod": {"minimum_readiness": 95.0, "minimum_coverage": 100.0, "blocking": True},
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate(
    environment: str,
    readiness: dict[str, Any],
    flow: dict[str, Any],
    bacen_tolerance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = POLICY[environment]
    readiness_percent = as_number(readiness.get("operational_readiness_percent"))
    coverage_percent = as_number(readiness.get("metric_coverage_percent"))
    ci_stability = as_number((readiness.get("indicators") or {}).get("ci_stability_percent"))
    source_flags = readiness.get("sources") or {}
    missing_sources = sorted(name for name, present in source_flags.items() if present is not True)

    flow_status = str(flow.get("status") or flow.get("overall_status") or "unknown").lower()
    critical_pending = int(flow.get("critical_pending") or flow.get("critical_open_count") or 0)
    flow_evidence_present = bool(flow)

    tolerance = bacen_tolerance or {}
    tolerance_present = bool(tolerance)
    tolerance_scope = str(tolerance.get("scope") or "").lower()
    tolerance_decision = str(tolerance.get("decision") or "unknown").lower()
    tolerance_active = tolerance.get("policy_active") is True
    tolerated_controls = sorted(str(item) for item in (tolerance.get("tolerated_controls") or []))
    blocking_controls = sorted(str(item) for item in (tolerance.get("blocking_controls") or []))
    production_allowed = tolerance.get("production_deployment_allowed") is True
    tolerance_blocking = tolerance.get("automatic_blocking") is True or bool(blocking_controls)

    reasons: list[str] = []
    warnings: list[str] = []
    insufficient = False
    hard_bacen_block = False

    if readiness_percent is None or coverage_percent is None:
        insufficient = True
        reasons.append("readiness_or_coverage_missing")
    if missing_sources:
        insufficient = True
        reasons.append("required_sources_missing:" + ",".join(missing_sources))
    if not flow_evidence_present:
        warnings.append("flow_completion_evidence_missing")
    if readiness_percent is not None and readiness_percent < policy["minimum_readiness"]:
        reasons.append("readiness_below_threshold")
    if coverage_percent is not None and coverage_percent < policy["minimum_coverage"]:
        reasons.append("coverage_below_threshold")
    if ci_stability is not None and ci_stability < 90:
        reasons.append("ci_stability_below_90")
    if critical_pending > 0:
        reasons.append("critical_flows_pending")
    if flow_evidence_present and flow_status in {"blocked", "failed", "red", "vermelho"}:
        reasons.append("flow_completion_blocked")

    expected_scope = environment
    if environment in {"dev", "stg"}:
        if not tolerance_present:
            warnings.append("bacen_tolerance_evidence_missing")
        elif tolerance_scope not in {expected_scope, "pull_request"}:
            hard_bacen_block = True
            reasons.append("bacen_tolerance_scope_mismatch")
        elif tolerance_blocking or tolerance_decision != "allow" or not tolerance_active:
            hard_bacen_block = True
            reasons.append("bacen_nonprod_tolerance_blocked")
        elif tolerated_controls:
            warnings.append("bacen_partial_controls_temporarily_tolerated")
    else:
        if not tolerance_present:
            hard_bacen_block = True
            reasons.append("bacen_production_evidence_missing")
        elif tolerance_scope != "prod":
            hard_bacen_block = True
            reasons.append("bacen_tolerance_scope_mismatch")
        elif tolerance_blocking or tolerance_decision != "allow" or not production_allowed:
            hard_bacen_block = True
            reasons.append("bacen_partial_controls_block_production")

    if hard_bacen_block:
        decision = "blocked"
    elif insufficient:
        decision = "insufficient_evidence"
    elif reasons:
        decision = "blocked" if policy["blocking"] else "approved_with_warning"
    elif warnings:
        decision = "approved_with_warning"
    else:
        decision = "approved"

    should_fail_workflow = hard_bacen_block or (policy["blocking"] and decision != "approved")

    return {
        "schema_version": "1.1.0",
        "contract": "reqsys-environment-promotion-readiness-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "decision": decision,
        "blocking": policy["blocking"] or hard_bacen_block,
        "should_fail_workflow": should_fail_workflow,
        "correlation_id": readiness.get("correlation_id"),
        "thresholds": policy,
        "evidence": {
            "operational_readiness_percent": readiness_percent,
            "metric_coverage_percent": coverage_percent,
            "ci_stability_percent": ci_stability,
            "flow_status": flow_status,
            "critical_pending": critical_pending,
            "flow_evidence_present": flow_evidence_present,
            "bacen_tolerance_present": tolerance_present,
            "bacen_tolerance_scope": tolerance_scope or None,
            "bacen_tolerance_decision": tolerance_decision,
            "bacen_tolerance_active": tolerance_active,
            "bacen_tolerated_controls": tolerated_controls,
            "bacen_blocking_controls": blocking_controls,
            "bacen_production_allowed": production_allowed,
        },
        "reasons": sorted(set(reasons)),
        "warnings": sorted(set(warnings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=sorted(POLICY), required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--flow", type=Path, required=True)
    parser.add_argument("--bacen-tolerance", type=Path, required=False)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(
        args.environment,
        load_json(args.readiness),
        load_json(args.flow),
        load_json(args.bacen_tolerance) if args.bacen_tolerance else {},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"environment": result["environment"], "decision": result["decision"]}))
    return 1 if result["should_fail_workflow"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
