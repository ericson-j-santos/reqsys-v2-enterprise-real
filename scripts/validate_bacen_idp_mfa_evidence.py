#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {"pending_integration", "collected", "validated", "rejected"}
REQUIRED_FIELDS = {
    "schema_version",
    "control_id",
    "provider",
    "environment",
    "evidence_status",
    "mfa_enforced",
    "privileged_identities_total",
    "privileged_identities_with_mfa",
    "production_touched",
}


def load_document(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("A evidência deve ser um objeto JSON")
    return data


def validate(document: dict[str, Any], source_path: Path) -> dict[str, Any]:
    missing_fields = sorted(REQUIRED_FIELDS - document.keys())
    status = str(document.get("evidence_status", ""))
    total = int(document.get("privileged_identities_total", 0))
    with_mfa = int(document.get("privileged_identities_with_mfa", 0))
    reference = document.get("evidence_reference")
    collected_at = document.get("collected_at")

    findings: list[str] = []
    if missing_fields:
        findings.append("missing_required_fields")
    if document.get("control_id") != "BACEN-02":
        findings.append("invalid_control_id")
    if status not in ALLOWED_STATUSES:
        findings.append("invalid_evidence_status")
    if total < 0 or with_mfa < 0 or with_mfa > total:
        findings.append("invalid_identity_totals")
    if document.get("production_touched") is not False:
        findings.append("production_access_not_allowed")

    evidence_is_real = (
        status in {"collected", "validated"}
        and document.get("mfa_enforced") is True
        and total > 0
        and with_mfa == total
        and bool(reference)
        and bool(collected_at)
    )
    if status in {"collected", "validated"} and not evidence_is_real:
        findings.append("incomplete_real_evidence")

    structural_checks_passed = not findings
    normalized_status = "evidenced" if evidence_is_real and status == "validated" else "pending"

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "provider": str(document.get("provider", "unknown")),
        "environment": str(document.get("environment", "unknown")),
        "evidence_status": status,
        "normalized_mfa_status": normalized_status,
        "mfa_evidenced": normalized_status == "evidenced",
        "coverage": {
            "privileged_identities_total": total,
            "privileged_identities_with_mfa": with_mfa,
        },
        "missing_fields": missing_fields,
        "findings": findings,
        "structural_checks_passed": structural_checks_passed,
        "human_review_required": normalized_status != "evidenced",
        "production_touched": False,
    }


def build_log_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "control_id": result["control_id"],
        "environment": result["environment"],
        "evidence_status": result["evidence_status"],
        "normalized_mfa_status": result["normalized_mfa_status"],
        "mfa_evidenced": result["mfa_evidenced"],
        "structural_checks_passed": result["structural_checks_passed"],
        "findings_count": len(result["findings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida evidência MFA externa do BACEN-02")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = validate(load_document(args.input), args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(build_log_summary(result), ensure_ascii=False))
    return 0 if result["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
