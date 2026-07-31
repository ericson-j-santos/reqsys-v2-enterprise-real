#!/usr/bin/env python3
"""Build a non-applying BACEN formal-completion proposal after a valid HITL approval."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

CONTROL_RE = re.compile(r"\b(BACEN-\d{2})\b")


def load_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(text) if suffix in {".yaml", ".yml"} else json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def find_control(matrix: dict[str, Any], control_id: str) -> dict[str, Any]:
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("matrix controls must be a list")
    matches = [
        item for item in controls if isinstance(item, dict) and item.get("id") == control_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one matrix control for {control_id}")
    return matches[0]


def build_proposal(
    *,
    matrix: dict[str, Any],
    issue: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    if decision.get("contract") != "reqsys-hitl-approval-decision":
        raise ValueError("unsupported decision contract")
    if decision.get("status") != "approved" or decision.get("effective_decision") != "approve":
        raise ValueError("proposal requires an approved HITL decision")
    approval = decision.get("approval") or {}
    actor = str(approval.get("actor") or "").strip()
    permission = str(approval.get("permission") or "").strip()
    if not actor or actor.endswith("[bot]"):
        raise ValueError("approved decision must reference a human actor")
    if permission not in {"write", "maintain", "admin"}:
        raise ValueError("approved decision has insufficient permission")

    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    match = CONTROL_RE.search(f"{title}\n{body}")
    if not match:
        raise ValueError("issue does not identify a BACEN control")
    control_id = match.group(1)
    control = find_control(matrix, control_id)
    current_status = str(control.get("status") or "").strip()
    if current_status not in {"partial", "implemented"}:
        raise ValueError(f"unsupported current status: {current_status or 'missing'}")

    already_implemented = current_status == "implemented"
    candidate_status = current_status if already_implemented else "implemented"
    evidence_path = str(control.get("evidence") or "").strip()
    decision_reference = str((decision.get("evidence") or {}).get("immutable_reference") or "")
    issue_url = str(issue.get("url") or issue.get("html_url") or "").strip()
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-bacen-formal-completion-proposal",
        "control_id": control_id,
        "current_status": current_status,
        "candidate_status": candidate_status,
        "decision": "no_change_required" if already_implemented else "human_review_required",
        "proposal": {
            "matrix_path": "governance/bacen/BACEN-CONTROL-MATRIX.yaml",
            "evidence_path": evidence_path,
            "issue_url": issue_url,
            "decision_reference": decision_reference,
            "required_verifications": [
                "formal_reference_is_non_sensitive_and_traceable",
                "signed_or_validated_evidence_contract_is_complete",
                "control_specific_readiness_workflow_is_green",
                "governed_pull_request_is_reviewed_before_matrix_change",
            ],
        },
        "automatic_apply_allowed": False,
        "automatic_implementation_claim_allowed": False,
        "human_review_required": not already_implemented,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--issue", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_proposal(
        matrix=load_document(args.matrix),
        issue=load_document(args.issue),
        decision=load_document(args.decision),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
