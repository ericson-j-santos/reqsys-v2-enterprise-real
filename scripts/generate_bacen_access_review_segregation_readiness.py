#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

FINAL_REVIEW_STATUSES = {"completed", "approved", "rejected"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def parse_optional_date(value: Any, field: str, findings: list[str]) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        findings.append(f"invalid_{field}")
        return None


def normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def build_evidence(register_path: Path) -> dict[str, Any]:
    document = load_yaml(register_path)
    review = document.get("review")
    if not isinstance(review, dict):
        raise ValueError("O bloco review deve ser um objeto")

    findings: list[str] = []
    review_owner = str(document.get("review_owner") or "").strip()
    approval_owner = str(document.get("approval_owner") or "").strip()
    status = str(review.get("status") or "").strip()
    reviewer = str(review.get("reviewer") or "").strip()
    approved_by = str(review.get("approved_by") or "").strip()
    approved_at = parse_optional_date(review.get("approved_at"), "approved_at", findings)
    reviewed_at = parse_optional_date(review.get("reviewed_at"), "reviewed_at", findings)

    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")
    if not review_owner:
        findings.append("missing_review_owner")
    if not approval_owner:
        findings.append("missing_approval_owner")
    if review_owner and approval_owner and normalized(review_owner) == normalized(approval_owner):
        findings.append("owner_role_segregation_conflict")
    if reviewer and approved_by and normalized(reviewer) == normalized(approved_by):
        findings.append("reviewer_approver_identity_conflict")
    if reviewed_at and approved_at and approved_at < reviewed_at:
        findings.append("approval_before_review")
    if approved_at and approved_at > datetime.now(UTC).date():
        findings.append("approval_date_in_future")

    approval_reference_present = bool(str(review.get("approval_reference") or "").strip())
    approval_record_complete = all((approved_by, approved_at, approval_reference_present))
    formal_review_final = status in FINAL_REVIEW_STATUSES

    if formal_review_final and status == "approved" and not approval_record_complete:
        findings.append("approved_status_without_complete_approval_record")
    if not formal_review_final and any((approved_by, approved_at, approval_reference_present)):
        findings.append("approval_data_present_before_final_review")
    if approved_by and not approved_at:
        findings.append("approver_without_approval_date")
    if approved_at and not approved_by:
        findings.append("approval_date_without_approver")

    structural_checks_passed = not findings
    role_segregation_ready = (
        bool(review_owner)
        and bool(approval_owner)
        and normalized(review_owner) != normalized(approval_owner)
    )
    identity_segregation_evidenced = (
        bool(reviewer)
        and bool(approved_by)
        and normalized(reviewer) != normalized(approved_by)
        and approval_record_complete
    )
    readiness_status = (
        "evidenced"
        if structural_checks_passed and role_segregation_ready and identity_segregation_evidenced
        else "pending"
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_status": status,
        "review_owner": review_owner or None,
        "approval_owner": approval_owner or None,
        "role_segregation_ready": role_segregation_ready,
        "reviewer_present": bool(reviewer),
        "approver_present": bool(approved_by),
        "approval_record_complete": approval_record_complete,
        "identity_segregation_evidenced": identity_segregation_evidenced,
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "human_action_required": not identity_segregation_evidenced,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida segregação de funções da revisão de acessos BACEN-02"
    )
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "control_id": evidence["control_id"],
                "role_segregation_ready": evidence["role_segregation_ready"],
                "identity_segregation_evidenced": evidence["identity_segregation_evidenced"],
                "structural_checks_passed": evidence["structural_checks_passed"],
                "findings_count": len(evidence["findings"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
