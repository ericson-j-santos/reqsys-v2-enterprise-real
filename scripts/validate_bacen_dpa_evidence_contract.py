#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

REQUIRED_FIELDS = {
    "vendor_id",
    "evidence_status",
    "document_reference",
    "document_sha256",
    "effective_at",
    "expires_at",
    "jurisdiction",
    "legal_approval_status",
    "legal_approval_reference",
}
HEX = set("0123456789abcdef")


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contrato YAML inválido")
    return data


def validate_record(record: dict, allowed_schemes: set[str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        errors.append(f"campos ausentes: {', '.join(missing)}")
        return errors
    digest = str(record["document_sha256"]).lower()
    if len(digest) != 64 or any(ch not in HEX for ch in digest):
        errors.append("document_sha256 inválido")
    reference = str(record["document_reference"])
    if urlparse(reference).scheme not in allowed_schemes:
        errors.append("document_reference usa esquema não permitido")
    if "content" in record or "document_content" in record:
        errors.append("conteúdo documental não pode ser armazenado")
    validated = record["evidence_status"] == "validated"
    approved = record["legal_approval_status"] == "approved"
    if validated and not approved:
        errors.append("evidência validada exige aprovação jurídica")
    return errors


def build_report(contract_path: Path) -> dict:
    contract = load_yaml(contract_path)
    records = contract.get("records") or []
    if not isinstance(records, list):
        raise ValueError("records deve ser lista")
    allowed_schemes = set(contract.get("privacy", {}).get("allowed_reference_schemes") or [])
    errors: dict[str, list[str]] = {}
    validated = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors[str(index)] = ["registro inválido"]
            continue
        record_errors = validate_record(record, allowed_schemes)
        if record_errors:
            errors[str(record.get("vendor_id", index))] = record_errors
        elif record["evidence_status"] == "validated":
            validated += 1
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "summary": {
            "total_records": len(records),
            "validated_records": validated,
            "invalid_records": len(errors),
        },
        "errors": errors,
        "result": "invalid" if errors else "valid",
        "automatic_blocking": bool(errors),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["result"] == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
