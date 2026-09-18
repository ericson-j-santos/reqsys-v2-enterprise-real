#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
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


def safe_reference(value: Any) -> bool:
    if value in (None, ""):
        return True
    raw = str(value).strip()
    if not raw or "://" in raw or raw.startswith(("/", "\\")):
        return False
    return ".." not in PurePosixPath(raw.replace("\\", "/")).parts


def nonnegative_int(value: Any, field: str, findings: list[str]) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        findings.append(f"invalid_{field}")
        return -1
    if parsed < 0:
        findings.append(f"negative_{field}")
    return parsed


def build_evidence(register_path: Path) -> dict[str, Any]:
    document = load_yaml(register_path)
    review = document.get("review")
    scope = document.get("scope")
    if not isinstance(review, dict) or not isinstance(scope, dict):
        raise ValueError("Os blocos review e scope devem ser objetos")

    findings: list[str] = []
    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")

    dimensions = {str(item) for item in (scope.get("review_dimensions") or [])}
    service_accounts_in_scope = "service_accounts" in dimensions
    if not service_accounts_in_scope:
        findings.append("service_accounts_not_in_review_scope")

    raw_coverage = document.get("service_account_review")
    coverage_present = raw_coverage is not None
    if raw_coverage is None:
        coverage: dict[str, Any] = {}
    elif isinstance(raw_coverage, dict):
        coverage = raw_coverage
    else:
        findings.append("service_account_review_must_be_object")
        coverage = {}

    total = nonnegative_int(coverage.get("total", 0), "service_accounts_total", findings)
    reviewed = nonnegative_int(coverage.get("reviewed", 0), "service_accounts_reviewed", findings)
    orphaned = nonnegative_int(coverage.get("orphaned", 0), "service_accounts_orphaned", findings)
    disabled = nonnegative_int(coverage.get("disabled", 0), "service_accounts_disabled", findings)
    exceptions_open = nonnegative_int(
        coverage.get("exceptions_open", 0),
        "service_account_exceptions_open",
        findings,
    )

    if total >= 0 and reviewed > total:
        findings.append("reviewed_service_accounts_exceed_total")
    if total >= 0 and orphaned > total:
        findings.append("orphaned_service_accounts_exceed_total")
    if total >= 0 and disabled > total:
        findings.append("disabled_service_accounts_exceed_total")
    if reviewed >= 0 and exceptions_open > reviewed:
        findings.append("service_account_exceptions_exceed_reviewed")

    reviewed_at = parse_optional_date(
        coverage.get("reviewed_at"),
        "service_account_reviewed_at",
        findings,
    )
    review_date = parse_optional_date(review.get("reviewed_at"), "reviewed_at", findings)
    today = datetime.now(UTC).date()
    if reviewed_at and reviewed_at > today:
        findings.append("service_account_review_date_in_future")
    if review_date and reviewed_at and reviewed_at > review_date:
        findings.append("service_account_review_after_formal_review")

    reference = coverage.get("evidence_reference")
    if not safe_reference(reference):
        findings.append("unsafe_service_account_evidence_reference")

    owner_coverage = coverage.get("owner_coverage_percent")
    owner_coverage_value: int | None = None
    if owner_coverage not in (None, ""):
        owner_coverage_value = nonnegative_int(
            owner_coverage,
            "owner_coverage_percent",
            findings,
        )
        if owner_coverage_value > 100:
            findings.append("owner_coverage_percent_above_100")

    review_status = str(review.get("status") or "")
    formal_review_final = review_status in FINAL_REVIEW_STATUSES
    complete_coverage = (
        coverage_present
        and total > 0
        and reviewed == total
        and bool(reviewed_at)
        and bool(str(reference or "").strip())
        and owner_coverage_value == 100
    )

    if formal_review_final and not complete_coverage:
        findings.append("formal_review_without_complete_service_account_coverage")
    if not formal_review_final and coverage_present and any(
        (
            total > 0,
            reviewed > 0,
            orphaned > 0,
            disabled > 0,
            exceptions_open > 0,
            reviewed_at,
            str(reference or "").strip(),
            owner_coverage_value not in (None, 0),
        )
    ):
        findings.append("service_account_evidence_before_formal_review")

    structural_checks_passed = not findings
    readiness_status = (
        "evidenced"
        if structural_checks_passed and formal_review_final and complete_coverage
        else "pending"
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_status": review_status,
        "service_accounts_in_scope": service_accounts_in_scope,
        "coverage_record_present": coverage_present,
        "coverage": {
            "total": total,
            "reviewed": reviewed,
            "orphaned": orphaned,
            "disabled": disabled,
            "exceptions_open": exceptions_open,
            "owner_coverage_percent": owner_coverage_value,
            "complete": complete_coverage,
        },
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "human_action_required": not complete_coverage,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida cobertura da revisão de contas de serviço BACEN-02"
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
                "coverage_record_present": evidence["coverage_record_present"],
                "structural_checks_passed": evidence["structural_checks_passed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
