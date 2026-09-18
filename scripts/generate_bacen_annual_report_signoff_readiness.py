#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONTROL_ID = "BACEN-08"
START_MARKER = "<!-- BACEN-08:SIGNOFF:START -->"
END_MARKER = "<!-- BACEN-08:SIGNOFF:END -->"
FORMALLY_SIGNED = "formally_signed"
REQUIRED_SIGNOFF_FIELDS = ("signed_by", "signed_at", "document_reference")
ALLOWED_REFERENCE_SCHEMES = {"https", "sharepoint", "vault"}


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_signoff(text: str) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    has_start = START_MARKER in text
    has_end = END_MARKER in text
    if has_start != has_end:
        return {}, ["unbalanced_signoff_markers"]
    if not has_start:
        return {}, []

    block = text.split(START_MARKER, 1)[1].split(END_MARKER, 1)[0]
    values: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        if normalized_key in {"status", *REQUIRED_SIGNOFF_FIELDS}:
            if normalized_key in values:
                errors.append(f"duplicate_signoff_field:{normalized_key}")
            values[normalized_key] = value.strip().strip("`")
    return values, errors


def _approval_table_valid(text: str) -> bool:
    if "## Aprovação" not in text:
        return False
    required_columns = ("Papel", "Nome", "Data", "Assinatura")
    header_pattern = re.compile(r"^\|[^\n]+\|$", re.MULTILINE)
    return any(all(column in row for column in required_columns) for row in header_pattern.findall(text))


def build_report(path: Path, now: datetime | None = None) -> dict[str, Any]:
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    text = path.read_text(encoding="utf-8")
    signoff, errors = _extract_signoff(text)
    findings: list[str] = []

    approval_section_present = "## Aprovação" in text
    approval_table_valid = _approval_table_valid(text)
    if not approval_section_present:
        errors.append("approval_section_missing")
    if not approval_table_valid:
        errors.append("approval_table_invalid")

    status = signoff.get("status", "pending_formal_signoff")
    missing_fields = [field for field in REQUIRED_SIGNOFF_FIELDS if not signoff.get(field)]
    signed_at: datetime | None = None
    if signoff.get("signed_at"):
        try:
            signed_at = _parse_datetime(signoff.get("signed_at"))
        except ValueError:
            errors.append("invalid_signed_at")
    if signed_at and signed_at > current_time:
        errors.append("signed_at_in_future")

    reference = signoff.get("document_reference")
    reference_scheme = urlparse(reference).scheme.lower() if reference else None
    if reference and reference_scheme not in ALLOWED_REFERENCE_SCHEMES:
        errors.append("invalid_signoff_reference_scheme")

    if status == FORMALLY_SIGNED and missing_fields:
        errors.append("formal_signoff_missing_required_fields")
    if status != FORMALLY_SIGNED:
        findings.append("annual_report_formal_signoff_pending")

    formally_valid = (
        status == FORMALLY_SIGNED
        and not missing_fields
        and signed_at is not None
        and reference_scheme in ALLOWED_REFERENCE_SCHEMES
        and approval_section_present
        and approval_table_valid
        and not errors
    )

    return {
        "schema_version": "1.0.0",
        "control_id": CONTROL_ID,
        "generated_at": current_time.isoformat(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "approval_section_present": approval_section_present,
        "approval_table_valid": approval_table_valid,
        "signoff_block_present": bool(signoff),
        "signoff_status": status,
        "missing_required_fields": missing_fields,
        "reference_scheme": reference_scheme,
        "formal_signoff_valid": formally_valid,
        "control_status": "implemented" if formally_valid else "partial",
        "automatic_blocking": bool(errors),
        "errors": sorted(set(errors)),
        "findings": sorted(set(findings)),
        "human_action_required": not formally_valid,
        "production_touched": False,
        "next_stage": "formal_annual_report_review_and_signoff",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera evidência de assinatura formal do relatório anual BACEN-08"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
