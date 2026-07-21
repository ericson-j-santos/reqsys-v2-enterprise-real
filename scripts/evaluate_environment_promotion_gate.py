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


def evaluate(environment: str, readiness: dict[str, Any], flow: dict[str, Any]) -> dict[str, Any]:
    policy = POLICY[environment]
    readiness_percent = as_number(readiness.get("operational_readiness_percent"))
    coverage_percent = as_number(readiness.get("metric_coverage_percent"))
    ci_stability = as_number((readiness.get("indicators") or {}).get("ci_stability_percent"))
    source_flags = readiness.get("sources") or {}
    missing_sources = sorted(name for name, present in source_flags.items() if present is not True)

    flow_status = str(flow.get("status") or flow.get("overall_status") or "unknown").lower()
    critical_pending = int(flow.get("critical_pending") or flow.get("critical_open_count") or 0)
    flow_evidence_present = bool(flow)

    reasons: list[str] = []
    warnings: list[str] = []
    insufficient = False

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

    if insufficient:
        decision = "insufficient_evidence"
    elif reasons:
        decision = "blocked" if policy["blocking"] else "approved_with_warning"
    elif warnings:
        decision = "approved_with_warning"
    else:
        decision = "approved"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-environment-promotion-readiness-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment,
        "decision": decision,
        "blocking": policy["blocking"],
        "should_fail_workflow": policy["blocking"] and decision != "approved",
        "correlation_id": readiness.get("correlation_id"),
        "thresholds": policy,
        "evidence": {
            "operational_readiness_percent": readiness_percent,
            "metric_coverage_percent": coverage_percent,
            "ci_stability_percent": ci_stability,
            "flow_status": flow_status,
            "critical_pending": critical_pending,
            "flow_evidence_present": flow_evidence_present,
        },
        "reasons": reasons,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=sorted(POLICY), required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--flow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.environment, load_json(args.readiness), load_json(args.flow))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"environment": result["environment"], "decision": result["decision"]}))
    return 1 if result["should_fail_workflow"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
