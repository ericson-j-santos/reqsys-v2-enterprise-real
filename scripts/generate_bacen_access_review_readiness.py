#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

REQUIRED_DIMENSIONS = {
    "least_privilege",
    "segregation_of_duties",
    "dormant_access",
    "privileged_access",
    "production_access",
    "service_accounts",
}
REQUIRED_PRIVILEGED_ROLES = {
    "SECURITY",
    "RUNTIME_OPERATOR",
    "GOVERNANCE",
    "PLATFORM_ADMIN",
}
FORMAL_REVIEW_STATUSES = {"completed", "approved"}
INSTITUTIONAL_STAGES = {"PRODUCTION", "INSTITUTIONAL"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def build_evidence(register_path: Path) -> dict[str, Any]:
    document = load_yaml(register_path)
    scope = document.get("scope") or {}
    review = document.get("review") or {}
    mfa = document.get("mfa") or {}
    if not all(isinstance(block, dict) for block in (scope, review, mfa)):
        raise ValueError("Blocos scope, review e mfa devem ser objetos")

    lifecycle_stage = str(document.get("lifecycle_stage") or "DEVELOPMENT").strip().upper()
    institutional_stage = lifecycle_stage in INSTITUTIONAL_STAGES
    deferred_contract = document.get("deferred_access_governance")
    deferred_enabled = isinstance(deferred_contract, dict) and deferred_contract.get("enabled") is True
    production_gate = (
        deferred_contract.get("production_gate")
        if isinstance(deferred_contract, dict)
        else None
    )

    structural_findings: list[str] = []
    if deferred_enabled and (
        not isinstance(production_gate, dict)
        or production_gate.get("block_production_when_missing") is not True
        or production_gate.get("formal_quarterly_review_required") is not True
        or production_gate.get("validated_mfa_evidence_required") is not True
    ):
        structural_findings.append("deferred_access_governance_production_gate_invalid")

    dimensions = set(scope.get("review_dimensions") or [])
    roles = set(scope.get("privileged_roles") or [])
    missing_dimensions = sorted(REQUIRED_DIMENSIONS - dimensions)
    missing_roles = sorted(REQUIRED_PRIVILEGED_ROLES - roles)

    cycle_days = int(document.get("review_cycle_days", 0))
    review_status = str(review.get("status", "unknown"))
    reviewed_at_raw = review.get("reviewed_at")
    reviewed_at = date.fromisoformat(str(reviewed_at_raw)) if reviewed_at_raw else None
    next_review_due_at = reviewed_at + timedelta(days=cycle_days) if reviewed_at else None
    review_overdue = bool(next_review_due_at and next_review_due_at < datetime.now(UTC).date())

    formal_review_completed = (
        review_status in FORMAL_REVIEW_STATUSES
        and bool(reviewed_at)
        and bool(review.get("reviewer"))
        and bool(review.get("approval_reference"))
        and int(review.get("identities_reviewed", 0)) > 0
    )
    mfa_evidenced = (
        str(mfa.get("evidence_status")) == "evidenced"
        and bool(mfa.get("evidence_reference"))
    )
    formal_governance_complete = formal_review_completed and mfa_evidenced

    deferred_in_current_stage = (
        deferred_enabled and not institutional_stage and not formal_governance_complete
    )
    production_gate_blocking = institutional_stage and not formal_governance_complete

    structural_checks_passed = (
        cycle_days == 90
        and not missing_dimensions
        and not missing_roles
        and not review_overdue
        and document.get("production_touched") is False
        and not structural_findings
    )

    findings: list[str] = []
    if missing_dimensions:
        findings.append("missing_review_dimensions")
    if missing_roles:
        findings.append("missing_privileged_roles")
    if review_overdue:
        findings.append("quarterly_access_review_overdue")
    if not formal_review_completed:
        findings.append("formal_quarterly_access_review_pending")
    if not mfa_evidenced:
        findings.append("identity_provider_mfa_evidence_pending")
    if deferred_in_current_stage:
        findings.append("formal_access_governance_deferred_until_institutionalization")
    if production_gate_blocking:
        findings.append("formal_access_governance_required_for_current_stage")
    findings.extend(structural_findings)

    implemented = structural_checks_passed and formal_governance_complete
    automatic_blocking = not structural_checks_passed or production_gate_blocking
    human_action_required = not formal_review_completed and not deferred_in_current_stage
    external_evidence_required = not mfa_evidenced and not deferred_in_current_stage

    if implemented:
        readiness_status = "formal_access_governance_validated"
        next_stage = "periodic_access_review"
    elif deferred_in_current_stage:
        readiness_status = "deferred_until_institutionalization"
        next_stage = "continue_technical_access_control_evidence_until_production_gate"
    else:
        readiness_status = "formal_access_governance_required"
        next_stage = "complete_formal_quarterly_review_and_ingest_validated_idp_mfa_evidence"

    return {
        "schema_version": "1.1.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "lifecycle_stage": lifecycle_stage,
        "institutional_stage": institutional_stage,
        "deferred_access_governance": deferred_enabled,
        "readiness_status": readiness_status,
        "review_cycle_days": cycle_days,
        "review_status": review_status,
        "formal_review_completed": formal_review_completed,
        "reviewed_at": str(reviewed_at) if reviewed_at else None,
        "next_review_due_at": str(next_review_due_at) if next_review_due_at else None,
        "review_overdue": review_overdue,
        "mfa_evidenced": mfa_evidenced,
        "formal_governance_complete": formal_governance_complete,
        "missing_review_dimensions": missing_dimensions,
        "missing_privileged_roles": missing_roles,
        "structural_checks_passed": structural_checks_passed,
        "control_status": "implemented" if implemented else "partial",
        "findings": sorted(set(findings)),
        "human_action_required": human_action_required,
        "external_evidence_required": external_evidence_required,
        "production_gate_blocking": production_gate_blocking,
        "automatic_blocking": automatic_blocking,
        "production_touched": False,
        "next_stage": next_stage,
    }


def build_log_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """Retorna somente campos operacionais permitidos para logs do CI."""
    return {
        "control_id": evidence["control_id"],
        "control_status": evidence["control_status"],
        "lifecycle_stage": evidence["lifecycle_stage"],
        "readiness_status": evidence["readiness_status"],
        "structural_checks_passed": evidence["structural_checks_passed"],
        "formal_review_completed": evidence["formal_review_completed"],
        "mfa_evidenced": evidence["mfa_evidenced"],
        "review_overdue": evidence["review_overdue"],
        "human_action_required": evidence["human_action_required"],
        "external_evidence_required": evidence["external_evidence_required"],
        "automatic_blocking": evidence["automatic_blocking"],
        "findings_count": len(evidence["findings"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera evidência BACEN-02 de revisão de acessos")
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(build_log_summary(evidence), ensure_ascii=False))
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
