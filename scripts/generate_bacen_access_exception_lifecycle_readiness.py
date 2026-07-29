#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

ALLOWED_STATUSES = {"open", "approved", "remediated", "expired", "rejected"}
ACTIVE_STATUSES = {"open", "approved"}
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

    try:
        declared_open = int(review.get("exceptions_open", 0))
    except (TypeError, ValueError):
        findings.append("invalid_exceptions_open")
        declared_open = -1
    if declared_open < 0:
        findings.append("negative_exceptions_open")

    raw_exceptions = document.get("exceptions")
    if raw_exceptions is None:
        exceptions: list[Any] = []
    elif isinstance(raw_exceptions, list):
        exceptions = raw_exceptions
    else:
        findings.append("exceptions_must_be_list")
        exceptions = []

    today = datetime.now(UTC).date()
    identifiers: set[str] = set()
    active_count = 0
    overdue_count = 0
    normalized: list[dict[str, Any]] = []

    for index, raw in enumerate(exceptions):
        prefix = f"exception_{index + 1}"
        if not isinstance(raw, dict):
            findings.append(f"{prefix}_must_be_object")
            continue

        identifier = str(raw.get("id") or "").strip()
        status = str(raw.get("status") or "").strip().lower()
        owner = str(raw.get("owner") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        opened_at = parse_optional_date(raw.get("opened_at"), f"{prefix}_opened_at", findings)
        expires_at = parse_optional_date(raw.get("expires_at"), f"{prefix}_expires_at", findings)
        closed_at = parse_optional_date(raw.get("closed_at"), f"{prefix}_closed_at", findings)
        approval_reference = raw.get("approval_reference")

        if not identifier:
            findings.append(f"{prefix}_missing_id")
        elif identifier in identifiers:
            findings.append("duplicate_exception_id")
        else:
            identifiers.add(identifier)
        if status not in ALLOWED_STATUSES:
            findings.append(f"{prefix}_invalid_status")
        if not owner:
            findings.append(f"{prefix}_missing_owner")
        if not reason:
            findings.append(f"{prefix}_missing_reason")
        if not opened_at:
            findings.append(f"{prefix}_missing_opened_at")
        if opened_at and expires_at and expires_at < opened_at:
            findings.append(f"{prefix}_expiry_before_opening")
        if opened_at and opened_at > today:
            findings.append(f"{prefix}_opened_at_in_future")
        if closed_at and opened_at and closed_at < opened_at:
            findings.append(f"{prefix}_closed_before_opening")
        if status in ACTIVE_STATUSES:
            active_count += 1
            if not expires_at:
                findings.append(f"{prefix}_missing_expiry")
            elif expires_at < today:
                overdue_count += 1
                findings.append(f"{prefix}_active_exception_overdue")
            if not safe_reference(approval_reference):
                findings.append(f"{prefix}_unsafe_approval_reference")
            if status == "approved" and not str(approval_reference or "").strip():
                findings.append(f"{prefix}_approved_without_reference")
        elif status in {"remediated", "rejected", "expired"} and not closed_at:
            findings.append(f"{prefix}_closed_status_without_closed_at")

        normalized.append(
            {
                "id": identifier or None,
                "status": status or None,
                "owner_present": bool(owner),
                "expires_at": str(expires_at) if expires_at else None,
                "overdue": bool(status in ACTIVE_STATUSES and expires_at and expires_at < today),
            }
        )

    if declared_open >= 0 and active_count != declared_open:
        findings.append("active_exception_count_mismatch")

    review_status = str(review.get("status") or "")
    formal_review_final = review_status in FINAL_REVIEW_STATUSES
    register_present = raw_exceptions is not None
    if formal_review_final and declared_open > 0 and not register_present:
        findings.append("formal_review_with_unregistered_exceptions")

    structural_checks_passed = not findings
    readiness_status = (
        "evidenced"
        if structural_checks_passed and formal_review_final and register_present
        else "pending"
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_status": review_status,
        "exception_register_present": register_present,
        "declared_open_exceptions": declared_open,
        "registered_exceptions": len(exceptions),
        "active_exceptions": active_count,
        "overdue_exceptions": overdue_count,
        "exceptions": normalized,
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "human_action_required": not formal_review_final or active_count > 0,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida ciclo de vida das exceções da revisão de acessos BACEN-02"
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
                "readiness_status": evidence["readiness_status"],
                "active_exceptions": evidence["active_exceptions"],
                "overdue_exceptions": evidence["overdue_exceptions"],
                "structural_checks_passed": evidence["structural_checks_passed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
