#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_REPORT_SECTIONS = {
    "Resumo executivo": ("Resumo executivo",),
    "Controles mínimos": (
        "Situação dos controles mínimos",
        "Panorama dos controles mínimos BACEN",
    ),
    "Incidentes de segurança do período": ("Incidentes de segurança do período",),
    "Avaliação de terceiros e nuvem": ("Avaliação de terceiros e nuvem",),
    "Plano de ação para o próximo ciclo": ("Plano de ação para o próximo ciclo",),
    "Responsável executivo": ("Responsável executivo",),
}
REQUIRED_DESIGNATION_FIELDS = (
    "executive_name",
    "executive_role",
    "designated_at",
    "designation_document_reference",
    "designated_by",
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def missing_required_sections(report_text: str) -> list[str]:
    missing: list[str] = []
    for section_name, accepted_headings in REQUIRED_REPORT_SECTIONS.items():
        if not any(f"## {heading}" in report_text for heading in accepted_headings):
            missing.append(section_name)
    return missing


def build_evidence(report_path: Path, designation_path: Path) -> dict[str, Any]:
    report_text = report_path.read_text(encoding="utf-8")
    designation_document = load_yaml(designation_path)
    designation = designation_document.get("designation") or {}
    if not isinstance(designation, dict):
        raise ValueError("Bloco designation inválido")

    missing_report_sections = missing_required_sections(report_text)
    designation_status = str(designation.get("status", "unknown"))
    missing_designation_fields = [
        field for field in REQUIRED_DESIGNATION_FIELDS if not designation.get(field)
    ]
    formal_designation_present = (
        designation_status == "formally_designated" and not missing_designation_fields
    )

    report_structurally_complete = not missing_report_sections
    technical_readiness_passed = report_structurally_complete
    formal_report_signoff_present = (
        formal_designation_present
        and "status: formally_signed" in report_text
        and "signed_by:" in report_text
        and "signed_at:" in report_text
    )

    findings: list[str] = []
    if missing_report_sections:
        findings.append("annual_report_missing_required_sections")
    if not formal_designation_present:
        findings.append("formal_executive_designation_pending")
    if not formal_report_signoff_present:
        findings.append("annual_report_formal_signoff_pending")

    return {
        "schema_version": "1.0.1",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "report_path": str(report_path),
        "designation_path": str(designation_path),
        "report_sha256": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        "designation_sha256": hashlib.sha256(designation_path.read_bytes()).hexdigest(),
        "report_structurally_complete": report_structurally_complete,
        "missing_report_sections": missing_report_sections,
        "accepted_report_section_headings": REQUIRED_REPORT_SECTIONS,
        "designation_status": designation_status,
        "formal_designation_present": formal_designation_present,
        "missing_designation_fields": missing_designation_fields,
        "formal_report_signoff_present": formal_report_signoff_present,
        "technical_readiness_passed": technical_readiness_passed,
        "control_status": (
            "implemented"
            if formal_designation_present and formal_report_signoff_present
            else "partial"
        ),
        "findings": findings,
        "automatic_blocking": False,
        "human_action_required": not (
            formal_designation_present and formal_report_signoff_present
        ),
        "production_touched": False,
        "next_stage": "formal_executive_designation_and_signed_annual_report",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera evidência de prontidão executiva BACEN-08")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--designation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.report, args.designation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["technical_readiness_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
