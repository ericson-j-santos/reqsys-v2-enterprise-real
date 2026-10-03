#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

CONTROL_ID = "BACEN-08"
FORMALLY_DESIGNATED = "formally_designated"
PENDING_DESIGNATION = "pending_formal_designation"
ALLOWED_STATUSES = {FORMALLY_DESIGNATED, PENDING_DESIGNATION, "revoked"}
REQUIRED_FORMAL_FIELDS = (
    "executive_name",
    "executive_role",
    "designated_at",
    "designation_document_reference",
    "designated_by",
)
ALLOWED_REFERENCE_SCHEMES = {"https", "sharepoint", "vault"}
INSTITUTIONAL_STAGES = {"PRODUCTION", "INSTITUTIONAL"}


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("documento de designação inválido")
    return payload


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _reference_scheme(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return urlparse(value.strip()).scheme.lower() or None


def build_report(path: Path, now: datetime | None = None) -> dict[str, Any]:
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    payload = _load_yaml(path)
    designation = payload.get("designation")
    errors: list[str] = []
    findings: list[str] = []

    if payload.get("control_id") != CONTROL_ID:
        errors.append("invalid_control_id")
    if not isinstance(designation, dict):
        errors.append("invalid_designation_block")
        designation = {}

    lifecycle_stage = str(payload.get("lifecycle_stage", "")).strip().upper()
    if not lifecycle_stage:
        errors.append("lifecycle_stage_missing")
    institutional_stage = lifecycle_stage in INSTITUTIONAL_STAGES

    deferred_contract = payload.get("deferred_institutional_governance")
    deferred_enabled = isinstance(deferred_contract, dict) and deferred_contract.get("enabled") is True
    production_gate = (
        deferred_contract.get("production_gate")
        if isinstance(deferred_contract, dict)
        else None
    )
    if deferred_enabled and (
        not isinstance(production_gate, dict)
        or production_gate.get("block_production_when_missing") is not True
    ):
        errors.append("deferred_governance_production_gate_missing")

    status = str(designation.get("status", "unknown"))
    if status not in ALLOWED_STATUSES:
        errors.append("invalid_designation_status")

    review_cycle_days = payload.get("review_cycle_days")
    if not isinstance(review_cycle_days, int) or review_cycle_days <= 0:
        errors.append("invalid_review_cycle_days")
        review_cycle_days = 365

    missing_fields = [field for field in REQUIRED_FORMAL_FIELDS if not designation.get(field)]
    designated_at: datetime | None = None
    if designation.get("designated_at"):
        try:
            designated_at = _parse_datetime(designation.get("designated_at"))
        except ValueError:
            errors.append("invalid_designated_at")
    if designated_at and designated_at > current_time:
        errors.append("designated_at_in_future")

    reference_scheme = _reference_scheme(designation.get("designation_document_reference"))
    if designation.get("designation_document_reference") and reference_scheme not in ALLOWED_REFERENCE_SCHEMES:
        errors.append("invalid_designation_reference_scheme")

    if status == FORMALLY_DESIGNATED and missing_fields:
        errors.append("formal_designation_missing_required_fields")
    if status != FORMALLY_DESIGNATED:
        findings.append("formal_executive_designation_pending")

    age_days: int | None = None
    review_overdue = False
    if designated_at:
        age_days = max(0, (current_time - designated_at).days)
        review_overdue = age_days > review_cycle_days
        if review_overdue:
            findings.append("executive_designation_review_overdue")

    formally_valid = (
        status == FORMALLY_DESIGNATED
        and not missing_fields
        and designated_at is not None
        and reference_scheme in ALLOWED_REFERENCE_SCHEMES
        and not review_overdue
        and not errors
    )
    deferred_in_current_stage = deferred_enabled and not institutional_stage and not formally_valid
    production_gate_blocking = institutional_stage and not formally_valid

    if deferred_in_current_stage:
        findings.append("institutional_governance_deferred_until_promotion")
    if production_gate_blocking:
        findings.append("formal_executive_designation_required_for_current_stage")

    if formally_valid:
        next_stage = "periodic_review"
    elif deferred_in_current_stage:
        next_stage = "continue_technical_evidence_until_production_gate"
    else:
        next_stage = "formal_designation_required"

    automatic_blocking = bool(errors) or production_gate_blocking
    human_action_required = not formally_valid and not deferred_in_current_stage

    return {
        "schema_version": "1.1.0",
        "control_id": CONTROL_ID,
        "generated_at": current_time.isoformat(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "lifecycle_stage": lifecycle_stage,
        "institutional_stage": institutional_stage,
        "deferred_institutional_governance": deferred_enabled,
        "designation_status": status,
        "missing_required_fields": missing_fields,
        "designation_age_days": age_days,
        "review_cycle_days": review_cycle_days,
        "review_overdue": review_overdue,
        "reference_scheme": reference_scheme,
        "formal_designation_valid": formally_valid,
        "control_status": "implemented" if formally_valid else "partial",
        "automatic_blocking": automatic_blocking,
        "errors": sorted(set(errors)),
        "findings": sorted(set(findings)),
        "human_action_required": human_action_required,
        "production_touched": False,
        "next_stage": next_stage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera evidência do ciclo de vida da designação executiva BACEN-08"
    )
    parser.add_argument("--designation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.designation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
