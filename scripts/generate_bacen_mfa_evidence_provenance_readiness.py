#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

ALLOWED_STATUSES = {"pending_integration", "collected", "validated", "rejected"}
ALLOWED_ENVIRONMENTS = {"DEV", "STG", "PROD"}
REAL_EVIDENCE_STATUSES = {"collected", "validated"}
MAX_EVIDENCE_AGE_DAYS = 90


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("A evidência deve ser um objeto JSON")
    return data


def parse_optional_date(value: Any, field: str, findings: list[str]) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
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


def as_nonnegative_int(value: Any, field: str, findings: list[str]) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        findings.append(f"invalid_{field}")
        return -1
    if parsed < 0:
        findings.append(f"negative_{field}")
    return parsed


def build_evidence(contract_path: Path) -> dict[str, Any]:
    document = load_json(contract_path)
    findings: list[str] = []

    status = str(document.get("evidence_status") or "")
    environment = str(document.get("environment") or "").upper()
    provider = str(document.get("provider") or "").strip()
    source_system = str(document.get("source_system") or "").strip()
    reference = document.get("evidence_reference")

    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if status not in ALLOWED_STATUSES:
        findings.append("invalid_evidence_status")
    if environment not in ALLOWED_ENVIRONMENTS:
        findings.append("invalid_environment")
    if not provider:
        findings.append("missing_provider")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")
    if not is_safe_reference(reference):
        findings.append("unsafe_evidence_reference")

    total = as_nonnegative_int(
        document.get("privileged_identities_total", 0),
        "privileged_identities_total",
        findings,
    )
    with_mfa = as_nonnegative_int(
        document.get("privileged_identities_with_mfa", 0),
        "privileged_identities_with_mfa",
        findings,
    )
    if total >= 0 and with_mfa > total:
        findings.append("mfa_identities_exceed_total")

    collected_at = parse_optional_date(document.get("collected_at"), "collected_at", findings)
    period_start = parse_optional_date(document.get("period_start"), "period_start", findings)
    period_end = parse_optional_date(document.get("period_end"), "period_end", findings)
    today = datetime.now(UTC).date()

    if period_start and period_end and period_start > period_end:
        findings.append("evidence_period_inverted")
    if period_end and collected_at and period_end > collected_at:
        findings.append("collected_before_period_end")
    if any(value and value > today for value in (period_start, period_end, collected_at)):
        findings.append("evidence_date_in_future")

    evidence_age_days = (today - collected_at).days if collected_at else None
    evidence_stale = bool(evidence_age_days is not None and evidence_age_days > MAX_EVIDENCE_AGE_DAYS)
    if status in REAL_EVIDENCE_STATUSES and evidence_stale:
        findings.append("mfa_evidence_stale")

    real_fields_present = all(
        (
            source_system,
            str(reference or "").strip(),
            collected_at,
            period_start,
            period_end,
            total > 0,
            document.get("mfa_enforced") is True,
        )
    )
    coverage_complete = total > 0 and with_mfa == total
    validated_evidence_ready = (
        status == "validated"
        and real_fields_present
        and coverage_complete
        and not evidence_stale
    )

    if status in REAL_EVIDENCE_STATUSES and not real_fields_present:
        findings.append("incomplete_mfa_provenance")
    if status == "validated" and not coverage_complete:
        findings.append("validated_mfa_coverage_incomplete")
    if status not in REAL_EVIDENCE_STATUSES and any(
        (
            source_system,
            str(reference or "").strip(),
            collected_at,
            period_start,
            period_end,
            total > 0,
            with_mfa > 0,
            document.get("mfa_enforced") is not None,
        )
    ):
        findings.append("evidence_data_present_before_collection")

    structural_checks_passed = not findings
    readiness_status = (
        "evidenced" if structural_checks_passed and validated_evidence_ready else "pending"
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "contract_path": str(contract_path),
        "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "provider": provider or None,
        "environment": environment or None,
        "evidence_status": status,
        "source_system_present": bool(source_system),
        "evidence_reference_present": bool(str(reference or "").strip()),
        "evidence_age_days": evidence_age_days,
        "evidence_stale": evidence_stale,
        "coverage": {
            "privileged_identities_total": total,
            "privileged_identities_with_mfa": with_mfa,
            "complete": coverage_complete,
        },
        "validated_evidence_ready": validated_evidence_ready,
        "readiness_status": readiness_status,
        "structural_checks_passed": structural_checks_passed,
        "external_evidence_required": not validated_evidence_ready,
        "findings": sorted(set(findings)),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida proveniência, temporalidade e cobertura da evidência MFA BACEN-02"
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "control_id": evidence["control_id"],
                "evidence_status": evidence["evidence_status"],
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
