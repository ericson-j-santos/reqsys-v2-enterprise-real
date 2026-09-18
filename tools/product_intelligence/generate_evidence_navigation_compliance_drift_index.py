#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_LIFECYCLE_INDEX = "product-intelligence-evidence-navigation-governance-lifecycle-index.json"
REQUIRED_MODE = "review_only"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required lifecycle index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def evaluate_drift(lifecycle_index: dict[str, Any]) -> dict[str, Any]:
    drifts: list[dict[str, Any]] = []

    if lifecycle_index.get("mode") != REQUIRED_MODE:
        drifts.append({"code": "MODE_DRIFT", "severity": "high", "detail": "Lifecycle index is not review_only"})
    if lifecycle_index.get("production_promotion_authorized") is not False:
        drifts.append({"code": "PRODUCTION_PROMOTION_DRIFT", "severity": "critical", "detail": "Production promotion must remain blocked"})
    if lifecycle_index.get("human_governance_review_required") is not True:
        drifts.append({"code": "HUMAN_REVIEW_DRIFT", "severity": "high", "detail": "Human governance review must remain required"})
    if lifecycle_index.get("lifecycle_complete") is not True:
        drifts.append({"code": "LIFECYCLE_COMPLETENESS_DRIFT", "severity": "high", "detail": "Lifecycle index is not complete"})

    lifecycle_map = lifecycle_index.get("lifecycle_map", [])
    if not isinstance(lifecycle_map, list) or not lifecycle_map:
        drifts.append({"code": "LIFECYCLE_MAP_MISSING", "severity": "high", "detail": "Lifecycle map must not be empty"})
    else:
        for item in lifecycle_map:
            if not isinstance(item, dict):
                continue
            artifact = str(item.get("artifact", "unknown-artifact"))
            if item.get("production_promotion_authorized") is not False:
                drifts.append({"code": "ARTIFACT_PROMOTION_DRIFT", "severity": "critical", "artifact": artifact, "detail": "Artifact production promotion is not blocked"})
            if item.get("requires_human_governance_review") is not True:
                drifts.append({"code": "ARTIFACT_REVIEW_DRIFT", "severity": "high", "artifact": artifact, "detail": "Artifact human review is not required"})
            if not item.get("sha256"):
                drifts.append({"code": "ARTIFACT_HASH_DRIFT", "severity": "medium", "artifact": artifact, "detail": "Artifact SHA-256 is missing"})
            if item.get("state") != "LIFECYCLE_REVIEW_ONLY_READY":
                drifts.append({"code": "ARTIFACT_STATE_DRIFT", "severity": "medium", "artifact": artifact, "detail": "Artifact state is not review-only ready"})

    critical_count = sum(1 for drift in drifts if drift.get("severity") == "critical")
    high_count = sum(1 for drift in drifts if drift.get("severity") == "high")
    compliant = not drifts

    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-compliance-drift-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": REQUIRED_MODE,
        "source": REQUIRED_LIFECYCLE_INDEX,
        "readiness_state": "EVIDENCE_NAVIGATION_COMPLIANCE_DRIFT_CLEAR" if compliant else "EVIDENCE_NAVIGATION_COMPLIANCE_DRIFT_DETECTED",
        "compliance_drift_clear": compliant,
        "drift_count": len(drifts),
        "critical_drift_count": critical_count,
        "high_drift_count": high_count,
        "confidence_percent": 98 if compliant else 74,
        "risk_percent": 1 if compliant else min(95, 25 + critical_count * 30 + high_count * 15),
        "production_promotion_authorized": False,
        "human_governance_review_required": True,
        "drifts": drifts,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if payload["drifts"]:
        rows = "\n".join(
            f"| {item.get('code')} | {item.get('severity')} | {item.get('artifact', '-')} | {item.get('detail')} |"
            for item in payload["drifts"]
        )
    else:
        rows = "| - | - | - | No compliance drift detected |"
    return f'''# Product Intelligence Evidence Navigation Compliance Drift Index

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Drift clear | {payload['compliance_drift_clear']} |
| Drift count | {payload['drift_count']} |
| Critical drift count | {payload['critical_drift_count']} |
| High drift count | {payload['high_drift_count']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Production promotion authorized | {payload['production_promotion_authorized']} |
| Human governance review required | {payload['human_governance_review_required']} |

## Drift map

| Code | Severity | Artifact | Detail |
|---|---|---|---|
{rows}

## Guardrail

This drift index blocks governance promotion whenever review-only mode, human review, hashing, lifecycle completeness or production-promotion controls drift from the expected state.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = evaluate_drift(load_json(report_dir / REQUIRED_LIFECYCLE_INDEX))
    (report_dir / "product-intelligence-evidence-navigation-compliance-drift-index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "product-intelligence-evidence-navigation-compliance-drift-index.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"Evidence navigation compliance drift index: {payload['readiness_state']} drift={payload['drift_count']} risk={payload['risk_percent']}%")
    return 0 if payload["compliance_drift_clear"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
