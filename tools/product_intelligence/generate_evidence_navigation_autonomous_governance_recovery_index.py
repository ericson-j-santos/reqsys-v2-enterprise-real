#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_DRIFT_INDEX = "product-intelligence-evidence-navigation-compliance-drift-index.json"

RECOVERY_PLAYBOOKS = {
    "MODE_DRIFT": "restore_review_only_mode",
    "PRODUCTION_PROMOTION_DRIFT": "block_production_promotion_and_require_human_review",
    "HUMAN_REVIEW_DRIFT": "restore_human_governance_review_requirement",
    "LIFECYCLE_COMPLETENESS_DRIFT": "regenerate_lifecycle_chain_from_source_workflows",
    "ARTIFACT_HASH_DRIFT": "regenerate_artifact_manifest_hashes",
    "ARTIFACT_STATE_DRIFT": "regenerate_review_only_artifact_state",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required compliance drift index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def build_recovery_index(drift_index: dict[str, Any]) -> dict[str, Any]:
    drifts = drift_index.get("drifts", [])
    if not isinstance(drifts, list):
        raise ValueError("drift index field 'drifts' must be a list")

    recovery_actions: list[dict[str, Any]] = []
    for drift in drifts:
        if not isinstance(drift, dict):
            continue
        code = str(drift.get("code", "UNKNOWN_DRIFT"))
        recovery_actions.append({
            "drift_code": code,
            "severity": drift.get("severity", "unknown"),
            "artifact": drift.get("artifact"),
            "recommended_playbook": RECOVERY_PLAYBOOKS.get(code, "manual_governance_triage"),
            "execution_mode": "human_approved_only",
            "automatic_execution_authorized": False,
            "destructive_action_authorized": False,
            "requires_audit_trail": True,
        })

    drift_clear = drift_index.get("compliance_drift_clear") is True and not drifts
    recovery_ready = drift_index.get("mode") == "review_only" and drift_index.get("production_promotion_authorized") is False

    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-autonomous-governance-recovery-index",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": REQUIRED_DRIFT_INDEX,
        "readiness_state": "EVIDENCE_NAVIGATION_AUTONOMOUS_RECOVERY_STANDBY" if drift_clear and recovery_ready else "EVIDENCE_NAVIGATION_AUTONOMOUS_RECOVERY_ACTION_REQUIRED",
        "drift_clear": drift_clear,
        "recovery_ready": recovery_ready,
        "recovery_action_count": len(recovery_actions),
        "automatic_execution_authorized": False,
        "destructive_action_authorized": False,
        "production_promotion_authorized": False,
        "human_governance_review_required": True,
        "confidence_percent": 98 if drift_clear and recovery_ready else 76,
        "risk_percent": 1 if drift_clear and recovery_ready else 25,
        "recovery_actions": recovery_actions,
        "standby_policy": {
            "when_no_drift": "do_not_execute_recovery",
            "when_drift_detected": "prepare_human_approved_recovery_playbook",
            "audit_required": True,
            "rerun_source_workflows_first": True,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if payload["recovery_actions"]:
        rows = "\n".join(
            f"| {item['drift_code']} | {item['severity']} | {item.get('artifact') or '-'} | {item['recommended_playbook']} | {item['automatic_execution_authorized']} |"
            for item in payload["recovery_actions"]
        )
    else:
        rows = "| - | - | - | Standby: no drift detected | False |"
    return f'''# Product Intelligence Evidence Navigation Autonomous Governance Recovery Index

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Drift clear | {payload['drift_clear']} |
| Recovery ready | {payload['recovery_ready']} |
| Recovery actions | {payload['recovery_action_count']} |
| Automatic execution authorized | {payload['automatic_execution_authorized']} |
| Destructive action authorized | {payload['destructive_action_authorized']} |
| Production promotion authorized | {payload['production_promotion_authorized']} |
| Human governance review required | {payload['human_governance_review_required']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |

## Recovery map

| Drift code | Severity | Artifact | Recommended playbook | Auto execution |
|---|---|---|---|---:|
{rows}

## Guardrail

This index prepares governed recovery actions but never executes destructive changes, production promotion, secret changes, branch bypass, or autonomous remediation without explicit human approval and audit trail.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_recovery_index(load_json(report_dir / REQUIRED_DRIFT_INDEX))
    (report_dir / "product-intelligence-evidence-navigation-autonomous-governance-recovery-index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "product-intelligence-evidence-navigation-autonomous-governance-recovery-index.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"Evidence navigation autonomous governance recovery index: {payload['readiness_state']} actions={payload['recovery_action_count']} risk={payload['risk_percent']}%")
    return 0 if payload["recovery_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
