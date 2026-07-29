#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

APPROVED_VALUE = "formally_approved"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifesto DPA deve ser um objeto YAML")
    return payload


def build_report(manifest_path: Path) -> dict[str, Any]:
    manifest = load_yaml(manifest_path)
    vendors = manifest.get("vendors") or []
    if not isinstance(vendors, list):
        raise ValueError("bloco vendors deve ser uma lista")

    seen: set[str] = set()
    duplicate_ids: list[str] = []
    structurally_invalid: list[str] = []
    approved: list[str] = []
    pending: list[str] = []

    for index, vendor in enumerate(vendors):
        if not isinstance(vendor, dict):
            structurally_invalid.append(str(index))
            continue
        vendor_id = str(vendor.get("id") or "")
        if not vendor_id:
            structurally_invalid.append(str(index))
            continue
        if vendor_id in seen:
            duplicate_ids.append(vendor_id)
        seen.add(vendor_id)

        value = vendor.get("data_processing_terms")
        if value is None:
            structurally_invalid.append(vendor_id)
        elif value == APPROVED_VALUE:
            approved.append(vendor_id)
        else:
            pending.append(vendor_id)

    structural_errors = bool(duplicate_ids or structurally_invalid)
    complete = bool(vendors) and not structural_errors and not pending
    coverage = round((len(approved) / len(vendors) * 100), 2) if vendors else 0.0

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "source": str(manifest_path),
        "source_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "summary": {
            "total_vendors": len(vendors),
            "approved_processing_terms": len(approved),
            "pending_processing_terms": len(pending),
            "coverage_percent": coverage,
        },
        "approved_vendor_ids": sorted(approved),
        "pending_vendor_ids": sorted(pending),
        "duplicate_vendor_ids": sorted(set(duplicate_ids)),
        "structurally_invalid_vendor_ids": sorted(structurally_invalid),
        "technical_readiness_passed": not structural_errors,
        "formal_processing_terms_complete": complete,
        "control_status": "implemented" if complete else "partial",
        "automatic_blocking": structural_errors,
        "human_action_required": not complete,
        "production_touched": False,
        "next_stage": "obtain_formal_approval_for_pending_data_processing_terms",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera prontidão dos termos de processamento BACEN-05")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
