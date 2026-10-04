#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

TARGET_CRITICALITIES = {"critical", "high"}
ALLOWED_STATUSES = {"pending", "documented", "validated", "expired", "rejected"}


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


def build_report(
    register_path: Path,
    contract_path: Path,
    max_notification_sla_hours: int,
) -> dict[str, Any]:
    register = load_yaml(register_path)
    contract = load_yaml(contract_path)
    providers = register.get("providers")
    records = contract.get("records") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")
    if not isinstance(records, list):
        raise ValueError("records deve ser uma lista")
    if max_notification_sla_hours <= 0:
        raise ValueError("max_notification_sla_hours deve ser positivo")

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
    duplicate_record_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            findings.append(f"invalid_record_entry:{index}")
            continue
        vendor_id = normalized(record.get("vendor_id"))
        if not vendor_id:
            findings.append(f"missing_record_vendor_id:{index}")
            continue
        if vendor_id in records_by_vendor:
            duplicate_record_ids.add(vendor_id)
        records_by_vendor[vendor_id] = record
        if vendor_id not in seen_provider_ids:
            findings.append(f"unknown_vendor_record:{vendor_id}")

    findings.extend(
        f"duplicate_record_vendor_id:{vendor_id}"
        for vendor_id in duplicate_record_ids
    )

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
                    "incident_notification_status": "missing",
                    "terms_complete": False,
                }
            )
            continue

        status = normalized(
            record.get("incident_notification_status") or "pending"
        ).lower()
        if status not in ALLOWED_STATUSES:
            findings.append(f"invalid_incident_notification_status:{vendor_id}")

        terms_reference = normalized(record.get("incident_notification_reference"))
        contact_reference = normalized(record.get("incident_contact_reference"))
        if terms_reference and not is_safe_reference(terms_reference):
            findings.append(f"unsafe_incident_notification_reference:{vendor_id}")
        if contact_reference and not is_safe_reference(contact_reference):
            findings.append(f"unsafe_incident_contact_reference:{vendor_id}")

        raw_sla = record.get("notification_sla_hours")
        notification_sla_hours: int | None = None
        if raw_sla not in (None, ""):
            try:
                notification_sla_hours = int(raw_sla)
            except (TypeError, ValueError):
                findings.append(f"invalid_notification_sla_hours:{vendor_id}")
            else:
                if notification_sla_hours <= 0:
                    findings.append(f"non_positive_notification_sla_hours:{vendor_id}")

        effective_at = parse_optional_date(
            record.get("effective_at"), "effective_at", vendor_id, findings
        )
        expires_at = parse_optional_date(
            record.get("expires_at"), "expires_at", vendor_id, findings
        )
        if effective_at and expires_at and effective_at > expires_at:
            findings.append(f"incident_terms_period_inverted:{vendor_id}")
        if expires_at and expires_at < today and status == "validated":
            findings.append(f"validated_incident_terms_expired:{vendor_id}")

        validated = status == "validated"
        complete = all(
            (
                validated,
                terms_reference,
                contact_reference,
                notification_sla_hours is not None,
                notification_sla_hours is not None
                and notification_sla_hours <= max_notification_sla_hours,
                effective_at,
                expires_at,
                expires_at is not None and expires_at >= today,
            )
        )
        has_partial_data = any(
            (
                terms_reference,
                contact_reference,
                notification_sla_hours is not None,
                effective_at,
                expires_at,
            )
        )
        if validated and not complete:
            findings.append(f"validated_incident_terms_incomplete:{vendor_id}")
        if not validated and has_partial_data and status == "pending":
            findings.append(f"pending_incident_terms_with_partial_data:{vendor_id}")

        if complete:
            complete_count += 1
        else:
            pending_vendor_ids.append(vendor_id)

        evaluated.append(
            {
                "vendor_id": vendor_id,
                "record_present": True,
                "incident_notification_status": status,
                "terms_reference_present": bool(terms_reference),
                "contact_reference_present": bool(contact_reference),
                "notification_sla_hours": notification_sla_hours,
                "within_sla_threshold": (
                    notification_sla_hours is not None
                    and notification_sla_hours <= max_notification_sla_hours
                ),
                "effective_at": str(effective_at) if effective_at else None,
                "expires_at": str(expires_at) if expires_at else None,
                "terms_complete": complete,
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
        "max_notification_sla_hours": max_notification_sla_hours,
        "summary": {
            "target_vendors": target_count,
            "complete_terms": complete_count,
            "pending_terms": target_count - complete_count,
            "coverage_percent": round((complete_count / target_count * 100), 2)
            if target_count
            else 0.0,
        },
        "vendors": evaluated,
        "pending_vendor_ids": sorted(set(pending_vendor_ids)),
        "findings": sorted(set(findings)),
        "incident_notification_terms_ready": readiness_complete,
        "control_status": "implemented" if readiness_complete else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not readiness_complete,
        "production_touched": False,
        "next_stage": "ingest_validated_incident_notification_terms_and_contacts",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera prontidão de cláusulas de notificação de incidentes BACEN-05"
    )
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--max-notification-sla-hours", type=int, default=72)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        args.register,
        args.contract,
        args.max_notification_sla_hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
