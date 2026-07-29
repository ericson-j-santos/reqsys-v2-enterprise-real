#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_DPA_FIELDS = (
    "data_processing_terms",
    "data_location",
    "subprocessors",
    "portability",
    "termination_and_deletion",
    "legal_signoff",
)
APPROVED_VALUE = "formally_approved"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def provider_ids(register: dict[str, Any]) -> set[str]:
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("Bloco providers inválido")
    return {
        str(item.get("id"))
        for item in providers
        if isinstance(item, dict) and item.get("id")
    }


def build_evidence(register_path: Path, manifest_path: Path) -> dict[str, Any]:
    register = load_yaml(register_path)
    manifest = load_yaml(manifest_path)
    registered_ids = provider_ids(register)
    vendors = manifest.get("vendors") or []
    if not isinstance(vendors, list):
        raise ValueError("Bloco vendors inválido")

    manifest_ids: set[str] = set()
    duplicate_ids: list[str] = []
    missing_fields: dict[str, list[str]] = {}
    incomplete_vendors: list[str] = []
    formally_approved_vendors: list[str] = []

    for vendor in vendors:
        if not isinstance(vendor, dict) or not vendor.get("id"):
            raise ValueError("Fornecedor sem id no manifesto DPA")
        vendor_id = str(vendor["id"])
        if vendor_id in manifest_ids:
            duplicate_ids.append(vendor_id)
        manifest_ids.add(vendor_id)
        missing = [field for field in REQUIRED_DPA_FIELDS if not vendor.get(field)]
        if missing:
            missing_fields[vendor_id] = missing
        approved = all(vendor.get(field) == APPROVED_VALUE for field in REQUIRED_DPA_FIELDS)
        if approved:
            formally_approved_vendors.append(vendor_id)
        else:
            incomplete_vendors.append(vendor_id)

    untracked_vendors = sorted(registered_ids - manifest_ids)
    unknown_vendors = sorted(manifest_ids - registered_ids)
    structural_errors = bool(duplicate_ids or missing_fields or untracked_vendors or unknown_vendors)
    complete = bool(registered_ids) and not structural_errors and not incomplete_vendors

    findings: list[str] = []
    if duplicate_ids:
        findings.append("duplicate_vendor_ids")
    if missing_fields:
        findings.append("required_dpa_fields_missing")
    if untracked_vendors:
        findings.append("registered_vendors_without_dpa_manifest")
    if unknown_vendors:
        findings.append("dpa_manifest_contains_unknown_vendors")
    if incomplete_vendors:
        findings.append("dpa_or_legal_signoff_pending")

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "register_path": str(register_path),
        "manifest_path": str(manifest_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "summary": {
            "registered_vendors": len(registered_ids),
            "manifest_vendors": len(manifest_ids),
            "formally_approved_vendors": len(formally_approved_vendors),
            "pending_vendors": len(incomplete_vendors),
        },
        "untracked_vendors": untracked_vendors,
        "unknown_vendors": unknown_vendors,
        "duplicate_vendor_ids": sorted(set(duplicate_ids)),
        "missing_fields": missing_fields,
        "pending_vendor_ids": sorted(incomplete_vendors),
        "technical_readiness_passed": not structural_errors,
        "formal_dpa_and_legal_signoff_complete": complete,
        "control_status": "implemented" if complete else "partial",
        "automatic_blocking": structural_errors,
        "human_action_required": not complete,
        "findings": findings,
        "production_touched": False,
        "next_stage": "attach_verified_dpa_evidence_and_formal_legal_signoff",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera prontidão documental DPA do BACEN-05")
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.register, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("BACEN-05 DPA readiness evidence generated")
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
