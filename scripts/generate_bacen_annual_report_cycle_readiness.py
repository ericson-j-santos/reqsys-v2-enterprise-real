#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

CONTROL_ID = "BACEN-08"
REFERENCE_SECTION = "## Ciclo de referência"
PERIOD_LABEL = "Período coberto"
ISSUED_AT_LABEL = "Data de emissão formal"
PLACEHOLDER_TOKENS = ("preencher", "pendente", "quando aprovado", "*(")


def _extract_list_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"^-\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.casefold()
    return any(token in normalized for token in PLACEHOLDER_TOKENS)


def _parse_period_year(value: str) -> int:
    years = [int(item) for item in re.findall(r"(?<!\d)(20\d{2})(?!\d)", value)]
    if not years:
        raise ValueError("period_year_missing")
    return max(years)


def _parse_issue_date(value: str) -> date:
    normalized = value.strip().strip("`*")
    return date.fromisoformat(normalized)


def build_report(path: Path, now: datetime | None = None) -> dict[str, Any]:
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    findings: list[str] = []

    section_present = REFERENCE_SECTION in text
    if not section_present:
        errors.append("reference_cycle_section_missing")

    period_value = _extract_list_value(text, PERIOD_LABEL)
    issued_at_value = _extract_list_value(text, ISSUED_AT_LABEL)
    period_pending = _is_placeholder(period_value)
    issued_at_pending = _is_placeholder(issued_at_value)

    period_year: int | None = None
    if period_pending:
        findings.append("annual_report_period_pending")
    elif period_value:
        try:
            period_year = _parse_period_year(period_value)
        except ValueError:
            errors.append("invalid_report_period")

    issued_at: date | None = None
    if issued_at_pending:
        findings.append("annual_report_issue_date_pending")
    elif issued_at_value:
        try:
            issued_at = _parse_issue_date(issued_at_value)
        except ValueError:
            errors.append("invalid_report_issue_date")

    if period_year and period_year > current_time.year:
        errors.append("report_period_in_future")
    if issued_at and issued_at > current_time.date():
        errors.append("report_issue_date_in_future")

    review_overdue = False
    if period_year is not None:
        review_overdue = period_year < current_time.year - 1
        if review_overdue:
            findings.append("annual_report_cycle_overdue")

    cycle_ready = (
        section_present
        and period_year is not None
        and issued_at is not None
        and not review_overdue
        and not errors
    )

    return {
        "schema_version": "1.0.0",
        "control_id": CONTROL_ID,
        "generated_at": current_time.isoformat(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reference_cycle_section_present": section_present,
        "period_pending": period_pending,
        "period_year": period_year,
        "issue_date_pending": issued_at_pending,
        "issued_at": issued_at.isoformat() if issued_at else None,
        "review_overdue": review_overdue,
        "cycle_ready": cycle_ready,
        "control_status": "implemented" if cycle_ready else "partial",
        "automatic_blocking": bool(errors),
        "errors": sorted(set(errors)),
        "findings": sorted(set(findings)),
        "human_action_required": not cycle_ready,
        "production_touched": False,
        "next_stage": "complete_reference_period_and_formal_issue_date",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera evidência do ciclo anual do relatório BACEN-08"
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
