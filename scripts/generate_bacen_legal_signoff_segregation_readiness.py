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

TARGET_CRITICALITIES = {"critical", "high"}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def normalized(value: Any) -> str:
    return str(value or "").strip()


def parse_optional_date(
    value: Any,
    field: str,
    vendor_id: str,
    findings: list[str],
) -> date | None:
    raw = normalized(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        findings.append(f"invalid_{field}:{vendor_id}")
        return None


def is_safe_reference(value: Any) -> bool:
    raw = normalized(value)
    if not raw:
        return True
    if raw.startswith(("/", "\\")):
        return False
    if "://" in raw:
        scheme = raw.split("://", 1)[0].lower()
        return scheme in {"https", "sharepoint", "vault"}
    return ".." not in PurePosixPath(raw.replace("\\", "/")).parts


def build_report(register_path: Path, contract_path: Path) -> dict[str, Any]:
    register = load_yaml(register_path)
    contract = load_yaml(contract_path)
    providers = register.get("providers")
    records = contract.get("records") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")
    if not isinstance(records, list):
        raise ValueError("records deve ser uma lista")

    allowed_statuses = (
        contract.get("allowed_statuses", {}).get("legal_approval_status")
        or ["pending", "approved", "rejected"]
    )
    if not isinstance(allowed_statuses, list):
        raise ValueError("allowed_statuses.legal_approval_status deve ser uma lista")
    allowed_legal_statuses = {normalized(item).lower() for item in allowed_statuses}

    findings: list[str] = []
    target_vendor_ids: set[str] = set()
    seen_provider_ids: set[str] = set()

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            findings.append(f"invalid_provider_entry:{index}")
            continue
        vendor_id = normalized(provider.get("id"))
        if not vendor_id:
            findings.append(f"missing_vendor_id:{index}")
            continue
        if vendor_id in seen_provider_ids:
            findings.append(f"duplicate_provider_id:{vendor_id}")
        seen_provider_ids.add(vendor_id)
        if normalized(provider.get("criticality")).lower() in TARGET_CRITICALITIES:
            target_vendor_ids.add(vendor_id)

    records_by_vendor: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            findings.append(f"invalid_record_entry:{index}")
            continue
        vendor_id = normalized(record.get("vendor_id"))
        if not vendor_id:
            findings.append(f"missing_record_vendor_id:{index}")
            continue
        if vendor_id in records_by_vendor:
            findings.append(f"duplicate_record_vendor_id:{vendor_id}")
        records_by_vendor[vendor_id] = record
        if vendor_id not in seen_provider_ids:
            findings.append(f"unknown_vendor_record:{vendor_id}")

    evaluated: list[dict[str, Any]] = []
    pending_vendor_ids: list[str] = []
    complete_count = 0
    today = datetime.now(UTC).date()

    for vendor_id in sorted(target_vendor_ids):
        record = records_by_vendor.get(vendor_id)
        if record is None:
            pending_vendor_ids.append(vendor_id)
            evaluated.append(
                {
                    "vendor_id": vendor_id,
                    "record_present": False,
                    "legal_approval_status": "missing",
                    "segregated_signoff_complete": False,
                }
            )
            continue

        legal_status = normalized(
            record.get("legal_approval_status") or "pending"
        ).lower()
        if legal_status not in allowed_legal_statuses:
            findings.append(f"invalid_legal_approval_status:{vendor_id}")

        evidence_status = normalized(record.get("evidence_status")).lower()
        legal_approver = normalized(record.get("legal_approver"))
        evidence_validated_by = normalized(
            record.get("evidence_validated_by") or record.get("validated_by")
        )
        source_system = normalized(record.get("legal_source_system"))
        approval_reference = normalized(record.get("legal_approval_reference"))
        decision_sha256 = normalized(
            record.get("legal_decision_sha256")
            or record.get("approval_record_sha256")
        )
        approval_at = parse_optional_date(
            record.get("legal_approval_at"),
            "legal_approval_at",
            vendor_id,
            findings,
        )

        if approval_reference and not is_safe_reference(approval_reference):
            findings.append(f"unsafe_legal_approval_reference:{vendor_id}")
        if decision_sha256 and not SHA256_PATTERN.fullmatch(decision_sha256):
            findings.append(f"invalid_legal_decision_sha256:{vendor_id}")
        if approval_at and approval_at > today:
            findings.append(f"legal_approval_date_in_future:{vendor_id}")

        identities_distinct = (
            bool(legal_approver)
            and bool(evidence_validated_by)
            and legal_approver.casefold() != evidence_validated_by.casefold()
        )
        if legal_approver and evidence_validated_by and not identities_distinct:
            findings.append(f"legal_evidence_validator_conflict:{vendor_id}")

        approved = legal_status == "approved"
        complete = all(
            (
                approved,
                evidence_status == "validated",
                legal_approver,
                evidence_validated_by,
                identities_distinct,
                source_system,
                approval_reference,
                approval_at,
                decision_sha256,
                SHA256_PATTERN.fullmatch(decision_sha256),
            )
        )

        if approved and not complete:
            findings.append(f"approved_legal_signoff_incomplete:{vendor_id}")
        if approved and evidence_status != "validated":
            findings.append(f"legal_approval_without_validated_evidence:{vendor_id}")
        if not approved and any((legal_approver, approval_at, decision_sha256)):
            findings.append(
                f"approval_data_present_without_approved_status:{vendor_id}"
            )

        if complete:
            complete_count += 1
        else:
            pending_vendor_ids.append(vendor_id)

        evaluated.append(
            {
                "vendor_id": vendor_id,
                "record_present": True,
                "legal_approval_status": legal_status,
                "evidence_status": evidence_status or None,
                "legal_approver_present": bool(legal_approver),
                "evidence_validator_present": bool(evidence_validated_by),
                "identities_distinct": identities_distinct,
                "source_system_present": bool(source_system),
                "approval_reference_present": bool(approval_reference),
                "approval_at": str(approval_at) if approval_at else None,
                "decision_sha256_present": bool(decision_sha256),
                "segregated_signoff_complete": complete,
            }
        )

    target_count = len(target_vendor_ids)
    automatic_blocking = bool(findings)
    readiness_complete = (
        target_count > 0
        and complete_count == target_count
        and not automatic_blocking
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "contract_path": str(contract_path),
        "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "summary": {
            "target_vendors": target_count,
            "complete_segregated_signoff": complete_count,
            "pending_segregated_signoff": target_count - complete_count,
            "coverage_percent": round((complete_count / target_count * 100), 2)
            if target_count
            else 0.0,
        },
        "vendors": evaluated,
        "pending_vendor_ids": sorted(set(pending_vendor_ids)),
        "findings": sorted(set(findings)),
        "legal_signoff_segregation_ready": readiness_complete,
        "control_status": "implemented" if readiness_complete else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not readiness_complete,
        "production_touched": False,
        "next_stage": "record_distinct_evidence_validator_and_legal_approver_with_provenance",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera prontidão de segregação do parecer jurídico BACEN-05"
    )
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.register, args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
