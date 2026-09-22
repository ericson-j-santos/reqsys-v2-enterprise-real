#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def build_attestation(policy_path: Path, metadata_path: Path) -> dict[str, Any]:
    policy_text = policy_path.read_text(encoding="utf-8")
    metadata = load_yaml(metadata_path)

    required_sections = metadata.get("required_sections") or []
    missing_sections = [section for section in required_sections if f"## {section}" not in policy_text]

    next_review = date.fromisoformat(str(metadata["next_technical_review_due_at"]))
    review_overdue = next_review < datetime.now(UTC).date()
    approval_status = str(metadata.get("approval_status", "unknown"))
    formal_approval_present = approval_status == "approved" and bool(metadata.get("approval_record"))

    findings: list[str] = []
    if missing_sections:
        findings.append("missing_required_sections")
    if review_overdue:
        findings.append("technical_review_overdue")
    if not formal_approval_present:
        findings.append("formal_institutional_approval_pending")

    technical_checks_passed = not missing_sections and not review_overdue
    policy_sha256 = hashlib.sha256(policy_text.encode("utf-8")).hexdigest()
    metadata_sha256 = hashlib.sha256(metadata_path.read_bytes()).hexdigest()

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-01",
        "generated_at": datetime.now(UTC).isoformat(),
        "policy_path": str(policy_path),
        "metadata_path": str(metadata_path),
        "policy_sha256": policy_sha256,
        "metadata_sha256": metadata_sha256,
        "policy_version": metadata.get("policy_version"),
        "technical_owner": metadata.get("technical_owner"),
        "approval_status": approval_status,
        "formal_approval_present": formal_approval_present,
        "last_technical_review_at": metadata.get("last_technical_review_at"),
        "next_technical_review_due_at": metadata.get("next_technical_review_due_at"),
        "review_overdue": review_overdue,
        "required_sections": required_sections,
        "missing_sections": missing_sections,
        "technical_checks_passed": technical_checks_passed,
        "control_status": "partial" if not formal_approval_present else "implemented",
        "findings": findings,
        "production_touched": False,
        "next_stage": metadata.get("next_stage"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera atestação técnica BACEN-01")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_attestation(args.policy, args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["technical_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
