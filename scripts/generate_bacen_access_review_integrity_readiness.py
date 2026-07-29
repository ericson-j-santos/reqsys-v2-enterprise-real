#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

ALLOWED_REVIEW_STATUSES = {
    "pending_first_formal_review",
    "in_progress",
    "completed",
    "approved",
    "rejected",
}
FINAL_REVIEW_STATUSES = {"completed", "approved", "rejected"}
COUNT_FIELDS = (
    "identities_reviewed",
    "access_removed",
    "access_adjusted",
    "exceptions_open",
)


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


def is_safe_reference(value: Any) -> bool:
    if value in (None, ""):
        return True
    raw = str(value).strip()
    if not raw or "://" in raw or raw.startswith(("/", "\\")):
        return False
    normalized = raw.replace("\\", "/")
    return ".." not in PurePosixPath(normalized).parts


def build_evidence(register_path: Path) -> dict[str, Any]:
    document = load_yaml(register_path)
    review = document.get("review")
    if not isinstance(review, dict):
        raise ValueError("O bloco review deve ser um objeto")

    findings: list[str] = []
    status = str(review.get("status", ""))
    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")
    if status not in ALLOWED_REVIEW_STATUSES:
        findings.append("invalid_review_status")

    counts: dict[str, int] = {}
    for field in COUNT_FIELDS:
        raw = review.get(field, 0)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            findings.append(f"invalid_{field}")
            value = -1
        if value < 0:
            findings.append(f"negative_{field}")
        counts[field] = value

    period_start = parse_optional_date(review.get("period_start"), "period_start", findings)
    period_end = parse_optional_date(review.get("period_end"), "period_end", findings)
    reviewed_at = parse_optional_date(review.get("reviewed_at"), "reviewed_at", findings)
    today = datetime.now(UTC).date()

    if period_start and period_end and period_start > period_end:
        findings.append("review_period_inverted")
    if period_end and reviewed_at and period_end > reviewed_at:
        findings.append("reviewed_before_period_end")
    if any(value and value > today for value in (period_start, period_end, reviewed_at)):
        findings.append("review_date_in_future")

    reviewed = counts["identities_reviewed"]
    changed = counts["access_removed"] + counts["access_adjusted"]
    if reviewed >= 0 and changed > reviewed:
        findings.append("access_changes_exceed_identities_reviewed")
    if reviewed >= 0 and counts["exceptions_open"] > reviewed:
        findings.append("exceptions_exceed_identities_reviewed")

    approval_reference = review.get("approval_reference")
    if not is_safe_reference(approval_reference):
        findings.append("unsafe_approval_reference")

    required_final_fields_present = all(
        (
            period_start,
            period_end,
            reviewed_at,
            str(review.get("reviewer") or "").strip(),
            str(approval_reference or "").strip(),
            reviewed > 0,
        )
    )
    formal_review_present = status in FINAL_REVIEW_STATUSES and required_final_fields_present

    if status in FINAL_REVIEW_STATUSES and not required_final_fields_present:
        findings.append("incomplete_formal_review_record")
    if status not in FINAL_REVIEW_STATUSES and any(
        (
            period_start,
            period_end,
            reviewed_at,
            str(review.get("reviewer") or "").strip(),
            str(approval_reference or "").strip(),
            reviewed > 0,
            counts["access_removed"] > 0,
            counts["access_adjusted"] > 0,
            counts["exceptions_open"] > 0,
        )
    ):
        findings.append("review_data_present_before_final_status")

    structural_checks_passed = not findings
    readiness_status = "ready" if formal_review_present and structural_checks_passed else "pending"

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_status": status,
        "period_start": str(period_start) if period_start else None,
        "period_end": str(period_end) if period_end else None,
        "reviewed_at": str(reviewed_at) if reviewed_at else None,
        "counts": counts,
        "formal_review_present": formal_review_present,
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "human_action_required": not formal_review_present,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida integridade temporal e contábil da revisão de acessos BACEN-02"
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
                "readiness_status": evidence["readiness_status"],
                "structural_checks_passed": evidence["structural_checks_passed"],
                "findings_count": len(evidence["findings"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
