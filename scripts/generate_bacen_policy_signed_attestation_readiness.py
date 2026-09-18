#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml

PENDING_VALUES = {"", "pending", "pending_formal_designation", "none", "null"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def normalized(value: Any) -> str:
    return str(value or "").strip()


def safe_reference(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme:
        return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password
    path = PurePosixPath(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and path.parts[:2] in {("governance", "bacen"), ("artifacts", "bacen")}
    )


def parse_signed_at(value: Any) -> date | None:
    text = normalized(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def build_readiness(policy_path: Path, metadata_path: Path) -> dict[str, Any]:
    policy_bytes = policy_path.read_bytes()
    metadata = load_yaml(metadata_path)
    structural_findings: list[str] = []
    advisory_findings: list[str] = []

    if normalized(metadata.get("control_id")) != "BACEN-01":
        structural_findings.append("invalid_control_id")

    approval_status = normalized(metadata.get("approval_status"))
    approval_record = metadata.get("approval_record")
    attestation_present = approval_record is not None
    attestation_valid = False
    attestation_reference: str | None = None
    signed_at: str | None = None
    approver_role: str | None = None

    actual_policy_sha256 = hashlib.sha256(policy_bytes).hexdigest()
    policy_version = normalized(metadata.get("policy_version"))

    if approval_record is None:
        advisory_findings.append("signed_attestation_pending")
        if approval_status == "approved":
            structural_findings.append("approved_without_signed_attestation")
    elif not isinstance(approval_record, dict):
        structural_findings.append("approval_record_must_be_mapping")
    else:
        attestation_reference = normalized(approval_record.get("reference"))
        signed_at = normalized(approval_record.get("signed_at"))
        approver_role = normalized(approval_record.get("approver_role"))
        record_policy_version = normalized(approval_record.get("policy_version"))
        record_policy_sha256 = normalized(approval_record.get("policy_sha256")).lower()

        if not safe_reference(attestation_reference):
            structural_findings.append("unsafe_or_missing_attestation_reference")

        parsed_signed_at = parse_signed_at(signed_at)
        if parsed_signed_at is None:
            structural_findings.append("invalid_or_missing_signed_at")
        elif parsed_signed_at > datetime.now(UTC).date():
            structural_findings.append("signed_at_in_future")

        if approver_role.lower() in PENDING_VALUES:
            structural_findings.append("approver_role_missing")
        if record_policy_version != policy_version:
            structural_findings.append("policy_version_binding_mismatch")
        if record_policy_sha256 != actual_policy_sha256:
            structural_findings.append("policy_sha256_binding_mismatch")
        if approval_status != "approved":
            structural_findings.append("signed_attestation_without_approved_status")

        attestation_valid = not structural_findings

    structural_checks_passed = not structural_findings
    if attestation_valid and structural_checks_passed:
        readiness_status = "signed_attestation_validated"
    elif structural_checks_passed:
        readiness_status = "pending_signed_attestation"
    else:
        readiness_status = "invalid_attestation_contract"

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-01",
        "generated_at": datetime.now(UTC).isoformat(),
        "policy_path": str(policy_path),
        "metadata_path": str(metadata_path),
        "approval_status": approval_status,
        "attestation_present": attestation_present,
        "attestation_valid": attestation_valid,
        "attestation_reference": attestation_reference,
        "signed_at": signed_at,
        "approver_role": approver_role,
        "policy_version": policy_version,
        "policy_sha256": actual_policy_sha256,
        "structural_checks_passed": structural_checks_passed,
        "readiness_status": readiness_status,
        "structural_findings": structural_findings,
        "advisory_findings": advisory_findings,
        "control_status": "implemented" if readiness_status == "signed_attestation_validated" else "partial",
        "production_touched": False,
        "next_stage": "attach_signed_attestation_bound_to_policy_version_and_sha256",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia prontidão da atestação assinada BACEN-01")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_readiness(args.policy, args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
