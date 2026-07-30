#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.validate_bacen_dpa_evidence_contract import build_report, load_yaml
except ModuleNotFoundError:  # execução direta a partir de scripts/
    from validate_bacen_dpa_evidence_contract import build_report, load_yaml

HEX = set("0123456789abcdef")


def normalize_sha256(value: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(character not in HEX for character in digest):
        raise ValueError("expected_sha256 inválido")
    return digest


def decode_base64_environment(variable_name: str) -> bytes:
    encoded = os.environ.get(variable_name, "").strip()
    if not encoded:
        raise ValueError(f"secret {variable_name} não configurado")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("payload DPA não é base64 válido") from exc
    if not payload:
        raise ValueError("payload DPA vazio")
    return payload


def registered_vendor_ids(register_path: Path) -> set[str]:
    register = yaml.safe_load(register_path.read_text(encoding="utf-8"))
    if not isinstance(register, dict):
        raise ValueError("registro de terceiros inválido")
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser lista")
    identifiers = {
        str(provider.get("id"))
        for provider in providers
        if isinstance(provider, dict) and provider.get("id")
    }
    if not identifiers:
        raise ValueError("registro de terceiros sem fornecedores")
    return identifiers


def ingest_payload(
    payload: bytes,
    expected_sha256: str,
    *,
    register_path: Path,
    minimum_validated_records: int,
) -> tuple[dict[str, Any], bool]:
    if minimum_validated_records < 1:
        raise ValueError("minimum_validated_records deve ser positivo")

    expected = normalize_sha256(expected_sha256)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError("source_sha256_mismatch")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="bacen-05-dpa-", suffix=".yaml", delete=False) as handle:
            handle.write(payload)
            temporary_path = Path(handle.name)
        temporary_path.chmod(0o600)
        contract = load_yaml(temporary_path)
        report = build_report(temporary_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    records = contract.get("records") or []
    if not isinstance(records, list):
        raise ValueError("records deve ser lista")

    vendor_ids = [
        str(record.get("vendor_id"))
        for record in records
        if isinstance(record, dict) and record.get("vendor_id")
    ]
    duplicates = sorted(
        vendor_id for vendor_id, count in Counter(vendor_ids).items() if count > 1
    )
    registered = registered_vendor_ids(register_path)
    unknown = sorted(set(vendor_ids) - registered)
    validated_records = int(report["summary"]["validated_records"])

    privacy = contract.get("privacy") or {}
    privacy_safe = isinstance(privacy, dict) and privacy.get("store_document_content") is False
    control_valid = contract.get("control_id") == "BACEN-05"
    accepted = (
        report["result"] == "valid"
        and control_valid
        and privacy_safe
        and not duplicates
        and not unknown
        and validated_records >= minimum_validated_records
    )

    report["registry_validation"] = {
        "registered_vendor_count": len(registered),
        "referenced_vendor_count": len(set(vendor_ids)),
        "duplicate_vendor_ids": duplicates,
        "unknown_vendor_ids": unknown,
    }
    report["ingestion"] = {
        "mode": "governed_secret_payload",
        "expected_sha256_match": True,
        "raw_evidence_persisted": False,
        "control_id_valid": control_valid,
        "privacy_contract_valid": privacy_safe,
        "minimum_validated_records": minimum_validated_records,
        "accepted": accepted,
    }
    report["human_review_required"] = not accepted
    report["automatic_blocking"] = not accepted
    return report, accepted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingere referências DPA sem persistir conteúdo documental bruto"
    )
    parser.add_argument("--base64-env", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--minimum-validated-records", type=int, default=1)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        report, accepted = ingest_payload(
            decode_base64_environment(args.base64_env),
            args.expected_sha256,
            register_path=args.register,
            minimum_validated_records=args.minimum_validated_records,
        )
    except (ValueError, yaml.YAMLError, OSError) as exc:
        print(f"BACEN-05 governed DPA ingestion failed: {type(exc).__name__}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "BACEN-05 governed DPA ingestion completed: "
        f"accepted={str(accepted).lower()}"
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
