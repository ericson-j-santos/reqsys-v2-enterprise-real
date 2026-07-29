#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml

REQUIRED_REVIEW_TRIGGERS = {
    "relevant_security_incident",
    "regulatory_change",
    "material_architecture_change",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def normalized(value: Any) -> str:
    return str(value or "").strip()


def parse_date(value: Any) -> date | None:
    text = normalized(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def safe_reference(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme:
        return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def build_readiness(metadata_path: Path) -> dict[str, Any]:
    metadata = load_yaml(metadata_path)
    structural_findings: list[str] = []
    advisory_findings: list[str] = []

    if normalized(metadata.get("control_id")) != "BACEN-01":
        structural_findings.append("invalid_control_id")

    try:
        review_cycle_days = int(metadata.get("review_cycle_days"))
    except (TypeError, ValueError):
        review_cycle_days = 0
    if review_cycle_days < 1 or review_cycle_days > 3660:
        structural_findings.append("invalid_review_cycle_days")

    effective_from = parse_date(metadata.get("effective_from"))
    last_review = parse_date(metadata.get("last_technical_review_at"))
    next_review = parse_date(metadata.get("next_technical_review_due_at"))
    if effective_from is None:
        structural_findings.append("invalid_effective_from")
    if last_review is None:
        structural_findings.append("invalid_last_technical_review_at")
    if next_review is None:
        structural_findings.append("invalid_next_technical_review_due_at")

    expected_next_review: date | None = None
    if effective_from and last_review and effective_from > last_review:
        structural_findings.append("effective_date_after_last_review")
    if last_review and next_review and last_review >= next_review:
        structural_findings.append("next_review_not_after_last_review")
    if last_review and review_cycle_days > 0:
        expected_next_review = last_review + timedelta(days=review_cycle_days)
        if next_review and next_review != expected_next_review:
            structural_findings.append("next_review_cycle_mismatch")

    today = datetime.now(UTC).date()
    review_overdue = bool(next_review and next_review < today)
    if review_overdue:
        structural_findings.append("technical_review_overdue")
    if last_review and last_review > today:
        structural_findings.append("last_review_in_future")

    configured_triggers = {
        normalized(item)
        for item in (metadata.get("review_triggers") or [])
        if normalized(item)
    }
    missing_triggers = sorted(REQUIRED_REVIEW_TRIGGERS - configured_triggers)
    if missing_triggers:
        structural_findings.append("required_review_triggers_missing")

    review_event_register = normalized(metadata.get("review_event_register"))
    event_register_present = bool(review_event_register)
    if event_register_present:
        if not safe_reference(review_event_register):
            structural_findings.append("unsafe_review_event_register_reference")
    else:
        advisory_findings.append("review_event_register_pending")

    structural_checks_passed = not structural_findings
    readiness_status = "review_cycle_validated" if structural_checks_passed else "invalid_review_cycle"

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-01",
        "generated_at": datetime.now(UTC).isoformat(),
        "metadata_path": str(metadata_path),
        "effective_from": effective_from.isoformat() if effective_from else None,
        "last_technical_review_at": last_review.isoformat() if last_review else None,
        "next_technical_review_due_at": next_review.isoformat() if next_review else None,
        "expected_next_review_due_at": expected_next_review.isoformat() if expected_next_review else None,
        "review_cycle_days": review_cycle_days,
        "review_overdue": review_overdue,
        "configured_review_triggers": sorted(configured_triggers),
        "required_review_triggers": sorted(REQUIRED_REVIEW_TRIGGERS),
        "missing_review_triggers": missing_triggers,
        "review_event_register": review_event_register or None,
        "event_register_present": event_register_present,
        "structural_checks_passed": structural_checks_passed,
        "readiness_status": readiness_status,
        "structural_findings": structural_findings,
        "advisory_findings": advisory_findings,
        "control_status": "partial",
        "production_touched": False,
        "next_stage": "record_trigger_evaluations_and_preserve_review_decision_evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia coerência do ciclo de revisão BACEN-01")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_readiness(args.metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
