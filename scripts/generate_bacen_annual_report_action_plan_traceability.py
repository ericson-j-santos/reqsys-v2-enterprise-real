#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SECTION_HEADING = "Plano de ação para o próximo ciclo"
START_MARKER = "<!-- BACEN-08:ACTION-PLAN:START -->"
END_MARKER = "<!-- BACEN-08:ACTION-PLAN:END -->"
TARGET_STATUSES = {"partial", "gap"}
ALLOWED_ACTION_STATUSES = {"planned", "in_progress", "completed", "blocked"}
REQUIRED_COLUMNS = ("controle", "responsável", "ação", "prazo", "status", "referência")
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def extract_section(text: str, heading: str) -> str | None:
    matches = list(HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).strip() != heading:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return None


def extract_marker_block(section: str) -> tuple[str | None, bool]:
    has_start = START_MARKER in section
    has_end = END_MARKER in section
    if has_start != has_end:
        return None, True
    if not has_start:
        return None, False
    start = section.index(START_MARKER) + len(START_MARKER)
    end = section.index(END_MARKER, start)
    return section[start:end].strip(), False


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_markdown_table(block: str) -> tuple[list[dict[str, str]], list[str]]:
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], ["action_plan_table_missing"]
    headers = [normalize_header(cell) for cell in lines[0].strip("|").split("|")]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        return [], [f"missing_action_plan_column:{column}" for column in missing_columns]

    rows: list[dict[str, str]] = []
    findings: list[str] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            findings.append("action_plan_row_column_mismatch")
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows, findings


def safe_reference(value: str) -> bool:
    raw = value.strip().replace("\\", "/")
    if not raw:
        return False
    if "://" in raw:
        return raw.split("://", 1)[0].lower() in {"https", "sharepoint", "vault"}
    if raw.startswith("/"):
        return False
    return ".." not in PurePosixPath(raw).parts


def target_controls(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls deve ser uma lista")
    result: dict[str, dict[str, Any]] = {}
    for control in controls:
        if not isinstance(control, dict):
            continue
        control_id = str(control.get("id") or "").strip()
        status = str(control.get("status") or "").strip().lower()
        if control_id and status in TARGET_STATUSES:
            result[control_id] = control
    return result


def build_report(report_path: Path, matrix_path: Path) -> dict[str, Any]:
    report_text = report_path.read_text(encoding="utf-8")
    matrix = load_yaml(matrix_path)
    section = extract_section(report_text, SECTION_HEADING)
    targets = target_controls(matrix)
    findings: list[str] = []
    warnings: list[str] = []
    evaluated: list[dict[str, Any]] = []

    if section is None:
        findings.append("action_plan_section_missing")
        block = None
        unbalanced_markers = False
    else:
        block, unbalanced_markers = extract_marker_block(section)
        if unbalanced_markers:
            findings.append("action_plan_markers_unbalanced")
        elif block is None:
            warnings.append("structured_action_plan_pending")

    rows: list[dict[str, str]] = []
    if block is not None:
        rows, table_findings = parse_markdown_table(block)
        findings.extend(table_findings)

    seen_controls: set[str] = set()
    today = datetime.now(UTC).date()
    completed_targets: set[str] = set()

    for index, row in enumerate(rows):
        control_id = row.get("controle", "").strip()
        owner = row.get("responsável", "").strip()
        action = row.get("ação", "").strip()
        due_raw = row.get("prazo", "").strip()
        status = row.get("status", "").strip().lower()
        reference = row.get("referência", "").strip()

        if not control_id:
            findings.append(f"action_plan_control_missing:{index}")
        elif control_id in seen_controls:
            findings.append(f"duplicate_action_plan_control:{control_id}")
        elif control_id not in targets:
            findings.append(f"action_plan_unknown_or_non_pending_control:{control_id}")
        seen_controls.add(control_id)

        if not owner:
            findings.append(f"action_plan_owner_missing:{control_id or index}")
        if not action:
            findings.append(f"action_plan_action_missing:{control_id or index}")
        if status not in ALLOWED_ACTION_STATUSES:
            findings.append(f"invalid_action_plan_status:{control_id or index}")
        if not safe_reference(reference):
            findings.append(f"invalid_action_plan_reference:{control_id or index}")

        due_date: date | None = None
        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            findings.append(f"invalid_action_plan_due_date:{control_id or index}")
        if due_date and due_date < today and status not in {"completed", "blocked"}:
            findings.append(f"overdue_action_plan_item:{control_id or index}")

        complete = all(
            (
                control_id in targets,
                owner,
                action,
                due_date,
                status in ALLOWED_ACTION_STATUSES,
                safe_reference(reference),
            )
        )
        if complete and control_id:
            completed_targets.add(control_id)
        evaluated.append(
            {
                "control_id": control_id or None,
                "owner_present": bool(owner),
                "action_present": bool(action),
                "due_date": str(due_date) if due_date else None,
                "status": status or None,
                "reference_present": bool(reference),
                "traceability_complete": bool(complete),
            }
        )

    missing_target_controls = sorted(set(targets) - completed_targets)
    if block is not None and missing_target_controls:
        warnings.extend(
            f"action_plan_target_pending:{control_id}" for control_id in missing_target_controls
        )

    automatic_blocking = bool(findings)
    target_count = len(targets)
    traceability_complete = (
        target_count > 0
        and len(completed_targets) == target_count
        and not automatic_blocking
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "action_plan_section_present": section is not None,
        "structured_block_present": block is not None,
        "summary": {
            "target_controls": target_count,
            "traceable_controls": len(completed_targets),
            "pending_controls": target_count - len(completed_targets),
            "coverage_percent": round(len(completed_targets) / target_count * 100, 2)
            if target_count
            else 0.0,
        },
        "target_control_ids": sorted(targets),
        "items": evaluated,
        "missing_target_control_ids": missing_target_controls,
        "findings": sorted(set(findings)),
        "warnings": sorted(set(warnings)),
        "action_plan_traceability_complete": traceability_complete,
        "control_status": "implemented" if traceability_complete else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not traceability_complete,
        "production_touched": False,
        "next_stage": "record_owned_dated_and_evidence_linked_actions_for_partial_controls",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera rastreabilidade do plano anual de ação BACEN-08"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_report(args.report, args.matrix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence["summary"], ensure_ascii=False))
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
