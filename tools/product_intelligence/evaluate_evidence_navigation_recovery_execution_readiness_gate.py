#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_RECOVERY_INDEX = "product-intelligence-evidence-navigation-autonomous-governance-recovery-index.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required recovery index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def evaluate_gate(recovery_index: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    rules = {
        "automatic_execution_authorized": "AUTO_EXECUTION_ENABLED",
        "destructive_action_authorized": "DESTRUCTIVE_ACTION_ENABLED",
        "production_promotion_authorized": "PRODUCTION_PROMOTION_ENABLED",
    }
    if recovery_index.get("mode") != "review_only":
        blockers.append({"code": "MODE_NOT_REVIEW_ONLY", "severity": "critical", "detail": "Recovery index must remain review_only"})
    for field, code in rules.items():
        if recovery_index.get(field) is not False:
            blockers.append({"code": code, "severity": "critical", "detail": f"{field} must remain false"})
    if recovery_index.get("human_governance_review_required") is not True:
        blockers.append({"code": "HUMAN_REVIEW_NOT_REQUIRED", "severity": "high", "detail": "Human governance review must be required"})
    if recovery_index.get("recovery_ready") is not True:
        blockers.append({"code": "RECOVERY_NOT_READY", "severity": "high", "detail": "Recovery index is not ready"})

    recovery_actions = recovery_index.get("recovery_actions", [])
    if recovery_actions and not isinstance(recovery_actions, list):
        blockers.append({"code": "RECOVERY_ACTIONS_INVALID", "severity": "high", "detail": "Recovery actions must be a list"})
    elif isinstance(recovery_actions, list):
        for index, action in enumerate(recovery_actions):
            if not isinstance(action, dict):
                blockers.append({"code": "RECOVERY_ACTION_INVALID", "severity": "high", "detail": f"Recovery action {index} is invalid"})
                continue
            if action.get("automatic_execution_authorized") is not False:
                blockers.append({"code": "ACTION_AUTO_EXECUTION_ENABLED", "severity": "critical", "detail": f"Recovery action {index} enables automatic execution"})
            if action.get("destructive_action_authorized") is not False:
                blockers.append({"code": "ACTION_DESTRUCTIVE_ENABLED", "severity": "critical", "detail": f"Recovery action {index} enables destructive action"})
            if action.get("requires_audit_trail") is not True:
                blockers.append({"code": "ACTION_AUDIT_MISSING", "severity": "high", "detail": f"Recovery action {index} does not require audit trail"})

    gate_passed = not blockers
    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-recovery-execution-readiness-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": REQUIRED_RECOVERY_INDEX,
        "readiness_state": "RECOVERY_EXECUTION_READINESS_GATE_PASSED" if gate_passed else "RECOVERY_EXECUTION_READINESS_GATE_BLOCKED",
        "gate_passed": gate_passed,
        "blocker_count": len(blockers),
        "critical_blocker_count": sum(1 for blocker in blockers if blocker.get("severity") == "critical"),
        "high_blocker_count": sum(1 for blocker in blockers if blocker.get("severity") == "high"),
        "automatic_execution_authorized": False,
        "destructive_action_authorized": False,
        "production_promotion_authorized": False,
        "human_governance_review_required": True,
        "confidence_percent": 99 if gate_passed else 75,
        "risk_percent": 1 if gate_passed else 30,
        "blockers": blockers,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(f"| {item['code']} | {item['severity']} | {item['detail']} |" for item in payload["blockers"]) or "| - | - | No blockers detected |"
    return f'''# Product Intelligence Evidence Navigation Recovery Execution Readiness Gate

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_state']} |
| Gate passed | {payload['gate_passed']} |
| Blockers | {payload['blocker_count']} |
| Critical blockers | {payload['critical_blocker_count']} |
| High blockers | {payload['high_blocker_count']} |
| Automatic execution authorized | {payload['automatic_execution_authorized']} |
| Destructive action authorized | {payload['destructive_action_authorized']} |
| Production promotion authorized | {payload['production_promotion_authorized']} |
| Human governance review required | {payload['human_governance_review_required']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |

## Blocker map

| Code | Severity | Detail |
|---|---|---|
{rows}

## Guardrail

This gate evaluates readiness only. It does not execute remediation, production promotion, destructive operations, secret changes, or repository protection changes.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = evaluate_gate(load_json(report_dir / REQUIRED_RECOVERY_INDEX))
    (report_dir / "product-intelligence-evidence-navigation-recovery-execution-readiness-gate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "product-intelligence-evidence-navigation-recovery-execution-readiness-gate.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"Evidence navigation recovery execution readiness gate: {payload['readiness_state']} blockers={payload['blocker_count']} risk={payload['risk_percent']}%")
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
