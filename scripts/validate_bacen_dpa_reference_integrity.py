#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ALLOWED_SCHEMES = {"https", "sharepoint", "vault"}


def load_contract(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("contrato DPA inválido")
    return payload


def build_report(contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    records = contract.get("records") or []
    if not isinstance(records, list):
        raise ValueError("records deve ser lista")

    vendor_ids: list[str] = []
    references: list[str] = []
    digests: list[str] = []
    invalid_schemes: dict[str, str] = {}
    missing: dict[str, list[str]] = {}

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"registro {index} inválido")
        vendor_id = str(record.get("vendor_id") or f"index-{index}")
        reference = str(record.get("document_reference") or "")
        digest = str(record.get("document_sha256") or "").lower()
        required_missing = [name for name, value in {
            "vendor_id": record.get("vendor_id"),
            "document_reference": reference,
            "document_sha256": digest,
        }.items() if not value]
        if required_missing:
            missing[vendor_id] = required_missing
        vendor_ids.append(vendor_id)
        references.append(reference)
        digests.append(digest)
        scheme = urlparse(reference).scheme
        if reference and scheme not in ALLOWED_SCHEMES:
            invalid_schemes[vendor_id] = scheme or "missing"

    duplicate_vendor_ids = sorted(key for key, count in Counter(vendor_ids).items() if count > 1)
    duplicate_references = sorted(key for key, count in Counter(references).items() if key and count > 1)
    duplicate_digests = sorted(key for key, count in Counter(digests).items() if key and count > 1)
    blocking = bool(duplicate_vendor_ids or duplicate_references or invalid_schemes or missing)

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_records": len(records),
            "duplicate_vendor_ids": len(duplicate_vendor_ids),
            "duplicate_references": len(duplicate_references),
            "duplicate_digests": len(duplicate_digests),
            "invalid_schemes": len(invalid_schemes),
            "records_with_missing_fields": len(missing),
        },
        "duplicate_vendor_ids": duplicate_vendor_ids,
        "duplicate_document_references": duplicate_references,
        "duplicate_document_sha256": duplicate_digests,
        "invalid_reference_schemes": invalid_schemes,
        "missing_fields": missing,
        "automatic_blocking": blocking,
        "result": "invalid" if blocking else "valid",
        "duplicate_digest_review_required": bool(duplicate_digests),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida integridade de referências documentais DPA")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
