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
        "Panorama dos macrocontroles internos ReqSys",
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
INSTITUTIONAL_STAGES = {"PRODUCTION", "INSTITUTIONAL"}


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

    structural_findings: list[str] = []
    lifecycle_stage = str(designation_document.get("lifecycle_stage", "")).strip().upper()
    if not lifecycle_stage:
        structural_findings.append("lifecycle_stage_missing")

    deferred_contract = designation_document.get("deferred_institutional_governance")
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
        structural_findings.append("deferred_governance_production_gate_missing")

    institutional_stage = lifecycle_stage in INSTITUTIONAL_STAGES
    missing_report_sections = missing_required_sections(report_text)
    designation_status = str(designation.get("status", "unknown"))
    missing_designation_fields = [
        field for field in REQUIRED_DESIGNATION_FIELDS if not designation.get(field)
    ]
    formal_designation_present = (
        designation_status == "formally_designated" and not missing_designation_fields
    )

    report_structurally_complete = not missing_report_sections
    formal_report_signoff_present = (
        formal_designation_present
        and "status: formally_signed" in report_text
        and "signed_by:" in report_text
        and "signed_at:" in report_text
    )
    formal_governance_complete = formal_designation_present and formal_report_signoff_present
    deferred_in_current_stage = deferred_enabled and not institutional_stage and not formal_governance_complete
    production_gate_blocking = institutional_stage and not formal_governance_complete

    findings: list[str] = []
    if missing_report_sections:
        findings.append("annual_report_missing_required_sections")
    if not formal_designation_present:
        findings.append("formal_executive_designation_pending")
    if not formal_report_signoff_present:
        findings.append("annual_report_formal_signoff_pending")
    if deferred_in_current_stage:
        findings.append("institutional_governance_deferred_until_promotion")
    if production_gate_blocking:
        findings.append("institutional_governance_required_for_current_stage")

    technical_readiness_passed = report_structurally_complete and not structural_findings
    automatic_blocking = bool(structural_findings) or production_gate_blocking
    human_action_required = not formal_governance_complete and not deferred_in_current_stage

    if formal_governance_complete:
        readiness_status = "formal_governance_validated"
        next_stage = "periodic_executive_governance_review"
    elif deferred_in_current_stage:
        readiness_status = "deferred_until_institutionalization"
        next_stage = "continue_technical_evidence_until_production_gate"
    else:
        readiness_status = "formal_governance_required"
        next_stage = "formal_executive_designation_and_signed_annual_report"

    return {
        "schema_version": "1.1.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "report_path": str(report_path),
        "designation_path": str(designation_path),
        "report_sha256": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        "designation_sha256": hashlib.sha256(designation_path.read_bytes()).hexdigest(),
        "lifecycle_stage": lifecycle_stage,
        "institutional_stage": institutional_stage,
        "deferred_institutional_governance": deferred_enabled,
        "report_structurally_complete": report_structurally_complete,
        "missing_report_sections": missing_report_sections,
        "accepted_report_section_headings": REQUIRED_REPORT_SECTIONS,
        "designation_status": designation_status,
        "formal_designation_present": formal_designation_present,
        "missing_designation_fields": missing_designation_fields,
        "formal_report_signoff_present": formal_report_signoff_present,
        "formal_governance_complete": formal_governance_complete,
        "technical_readiness_passed": technical_readiness_passed,
        "readiness_status": readiness_status,
        "control_status": "implemented" if formal_governance_complete else "partial",
        "structural_findings": structural_findings,
        "findings": findings,
        "automatic_blocking": automatic_blocking,
        "human_action_required": human_action_required,
        "production_touched": False,
        "next_stage": next_stage,
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
    return 0 if evidence["technical_readiness_passed"] and not evidence["automatic_blocking"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
