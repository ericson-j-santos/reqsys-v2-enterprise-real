#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SECTION_HEADING = "Incidentes de segurança do período"
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
ALLOWED_CONTROL_STATUSES = {"implemented", "partial", "gap"}


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


def is_safe_repo_reference(value: Any) -> bool:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or "://" in raw:
        return False
    return ".." not in PurePosixPath(raw).parts


def find_control(matrix: dict[str, Any], control_id: str) -> tuple[dict[str, Any] | None, bool]:
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls deve ser uma lista")
    matches = [item for item in controls if isinstance(item, dict) and item.get("id") == control_id]
    return (matches[0] if matches else None, len(matches) > 1)


def build_report(report_path: Path, matrix_path: Path) -> dict[str, Any]:
    report_text = report_path.read_text(encoding="utf-8")
    matrix = load_yaml(matrix_path)
    section = extract_section(report_text, SECTION_HEADING)
    control, duplicate_control = find_control(matrix, "BACEN-03")
    findings: list[str] = []
    warnings: list[str] = []

    if section is None:
        findings.append("incident_section_missing")
    if duplicate_control:
        findings.append("duplicate_bacen_03_control")
    if control is None:
        findings.append("bacen_03_control_missing")
        control = {}

    status = str(control.get("status") or "").strip().lower()
    if status and status not in ALLOWED_CONTROL_STATUSES:
        findings.append("invalid_bacen_03_status")

    required_fields = ("evidence", "policy")
    recommended_fields = ("scenario",)
    evaluated: list[dict[str, Any]] = []
    missing_required: list[str] = []
    missing_recommended: list[str] = []

    for field in (*required_fields, *recommended_fields):
        reference = str(control.get(field) or "").strip()
        safe = is_safe_repo_reference(reference) if reference else False
        mentioned = bool(section and reference and reference in section)
        required = field in required_fields

        if required and not reference:
            findings.append(f"missing_bacen_03_{field}_reference")
        elif reference and not safe:
            findings.append(f"unsafe_bacen_03_{field}_reference")
        elif required and not mentioned:
            missing_required.append(field)
            findings.append(f"annual_report_missing_{field}_linkage")
        elif not required and reference and not mentioned:
            missing_recommended.append(field)
            warnings.append(f"annual_report_missing_recommended_{field}_linkage")

        evaluated.append(
            {
                "field": field,
                "required": required,
                "reference": reference or None,
                "safe_reference": safe,
                "mentioned_in_report": mentioned,
            }
        )

    automatic_blocking = bool(findings)
    required_linkage_complete = not missing_required and all(
        item["reference"] and item["safe_reference"]
        for item in evaluated
        if item["required"]
    )

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-08",
        "source_control_id": "BACEN-03",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "bacen_03_status": status or None,
        "incident_section_present": section is not None,
        "linkages": evaluated,
        "missing_required_linkages": sorted(missing_required),
        "missing_recommended_linkages": sorted(missing_recommended),
        "findings": sorted(set(findings)),
        "warnings": sorted(set(warnings)),
        "required_incident_linkage_complete": required_linkage_complete and not automatic_blocking,
        "control_status": "implemented" if required_linkage_complete and not automatic_blocking else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": bool(missing_recommended),
        "production_touched": False,
        "next_stage": "link_real_incident_metrics_without_fabricating_operational_data",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera vínculo de evidências BACEN-03 no relatório anual BACEN-08"
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
    print(
        json.dumps(
            {
                "required_linkage_complete": evidence["required_incident_linkage_complete"],
                "missing_recommended": evidence["missing_recommended_linkages"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
