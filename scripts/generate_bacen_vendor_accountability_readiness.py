#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

TARGET_CRITICALITIES = {"critical", "high"}
ALLOWED_CRITICALITIES = {"critical", "high", "medium", "low"}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def normalized(value: Any) -> str:
    return str(value or "").strip()


def is_safe_reference(value: Any) -> bool:
    raw = normalized(value)
    if not raw:
        return True
    if "://" in raw or raw.startswith(("/", "\\")):
        return False
    return ".." not in PurePosixPath(raw.replace("\\", "/")).parts


def build_report(register_path: Path) -> dict[str, Any]:
    register = load_yaml(register_path)
    providers = register.get("providers")
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")

    findings: list[str] = []
    duplicate_vendor_ids: set[str] = set()
    seen: set[str] = set()
    evaluated: list[dict[str, Any]] = []
    pending_vendor_ids: list[str] = []

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            findings.append(f"invalid_provider_entry:{index}")
            continue

        vendor_id = normalized(provider.get("id"))
        if not vendor_id:
            findings.append(f"missing_vendor_id:{index}")
            continue
        if vendor_id in seen:
            duplicate_vendor_ids.add(vendor_id)
        seen.add(vendor_id)

        criticality = normalized(provider.get("criticality")).lower()
        if criticality not in ALLOWED_CRITICALITIES:
            findings.append(f"invalid_criticality:{vendor_id}")
            continue
        if criticality not in TARGET_CRITICALITIES:
            continue

        business_owner = normalized(
            provider.get("business_owner") or provider.get("accountable_owner")
        )
        technical_owner = normalized(provider.get("technical_owner"))
        security_owner = normalized(provider.get("security_owner"))
        escalation_reference = normalized(
            provider.get("escalation_reference")
            or provider.get("escalation_contact_reference")
        )

        if escalation_reference and not is_safe_reference(escalation_reference):
            findings.append(f"unsafe_escalation_reference:{vendor_id}")

        owners = {
            value.casefold()
            for value in (business_owner, technical_owner, security_owner)
            if value
        }
        role_segregation_ready = len(owners) >= 2
        accountability_complete = all(
            (
                business_owner,
                technical_owner,
                security_owner,
                escalation_reference,
                role_segregation_ready,
            )
        )
        if not accountability_complete:
            pending_vendor_ids.append(vendor_id)

        evaluated.append(
            {
                "vendor_id": vendor_id,
                "provider": normalized(provider.get("provider")),
                "criticality": criticality,
                "business_owner_present": bool(business_owner),
                "technical_owner_present": bool(technical_owner),
                "security_owner_present": bool(security_owner),
                "escalation_reference_present": bool(escalation_reference),
                "role_segregation_ready": role_segregation_ready,
                "accountability_complete": accountability_complete,
            }
        )

    findings.extend(f"duplicate_vendor_id:{vendor_id}" for vendor_id in duplicate_vendor_ids)
    automatic_blocking = bool(findings)
    complete_count = sum(1 for item in evaluated if item["accountability_complete"])
    target_count = len(evaluated)
    accountability_ready = (
        target_count > 0 and complete_count == target_count and not automatic_blocking
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "source": str(register_path),
        "source_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "summary": {
            "target_vendors": target_count,
            "complete_accountability": complete_count,
            "pending_accountability": target_count - complete_count,
            "coverage_percent": round((complete_count / target_count * 100), 2)
            if target_count
            else 0.0,
        },
        "vendors": evaluated,
        "pending_vendor_ids": sorted(set(pending_vendor_ids)),
        "findings": sorted(set(findings)),
        "accountability_ready": accountability_ready,
        "control_status": "implemented" if accountability_ready else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not accountability_ready,
        "production_touched": False,
        "next_stage": "assign_business_technical_security_owners_and_escalation_references",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera prontidão de responsabilização de fornecedores BACEN-05"
    )
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
