#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

FINAL_REVIEW_STATUSES = {"completed", "approved", "rejected"}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def parse_optional_date(value: Any, field: str, findings: list[str]) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        findings.append(f"invalid_{field}")
        return None


def safe_reference(value: Any) -> bool:
    if value in (None, ""):
        return True
    raw = str(value).strip()
    if not raw or "://" in raw or raw.startswith(("/", "\\")):
        return False
    return ".." not in PurePosixPath(raw.replace("\\", "/")).parts


def build_evidence(register_path: Path) -> dict[str, Any]:
    document = load_yaml(register_path)
    review = document.get("review")
    if not isinstance(review, dict):
        raise ValueError("O bloco review deve ser um objeto")

    findings: list[str] = []
    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")

    status = str(review.get("status") or "").strip()
    reference = review.get("approval_reference")
    reference_present = bool(str(reference or "").strip())
    if not safe_reference(reference):
        findings.append("unsafe_approval_reference")

    approved_by = str(review.get("approved_by") or "").strip()
    approval_system = str(review.get("approval_system") or "").strip()
    approval_sha256 = str(review.get("approval_sha256") or "").strip()
    recorded_at = parse_optional_date(
        review.get("approval_recorded_at"),
        "approval_recorded_at",
        findings,
    )
    approved_at = parse_optional_date(review.get("approved_at"), "approved_at", findings)
    reviewed_at = parse_optional_date(review.get("reviewed_at"), "reviewed_at", findings)
    today = datetime.now(UTC).date()

    if approval_sha256 and not SHA256_PATTERN.fullmatch(approval_sha256):
        findings.append("invalid_approval_sha256")
    if recorded_at and recorded_at > today:
        findings.append("approval_recorded_at_in_future")
    if approved_at and approved_at > today:
        findings.append("approved_at_in_future")
    if reviewed_at and approved_at and approved_at < reviewed_at:
        findings.append("approval_before_review")
    if approved_at and recorded_at and recorded_at < approved_at:
        findings.append("approval_recorded_before_approval")

    provenance_fields = (
        reference_present,
        bool(approved_by),
        bool(approval_system),
        bool(approval_sha256),
        bool(recorded_at),
        bool(approved_at),
    )
    provenance_present = any(provenance_fields)
    provenance_complete = all(provenance_fields) and bool(
        SHA256_PATTERN.fullmatch(approval_sha256)
    )
    formal_review_final = status in FINAL_REVIEW_STATUSES

    if status == "approved" and not provenance_complete:
        findings.append("approved_review_without_complete_approval_provenance")
    if status in {"completed", "rejected"} and reference_present and not provenance_complete:
        findings.append("final_review_with_partial_approval_provenance")
    if not formal_review_final and provenance_present:
        findings.append("approval_provenance_before_final_review")

    structural_checks_passed = not findings
    readiness_status = (
        "evidenced"
        if structural_checks_passed and status == "approved" and provenance_complete
        else "pending"
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_status": status,
        "approval_reference_present": reference_present,
        "approved_by_present": bool(approved_by),
        "approval_system_present": bool(approval_system),
        "approval_sha256_present": bool(approval_sha256),
        "approval_recorded_at": str(recorded_at) if recorded_at else None,
        "approved_at": str(approved_at) if approved_at else None,
        "provenance_complete": provenance_complete,
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "human_action_required": not provenance_complete,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida proveniência da referência de aprovação BACEN-02"
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
                "review_status": evidence["review_status"],
                "provenance_complete": evidence["provenance_complete"],
                "structural_checks_passed": evidence["structural_checks_passed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
