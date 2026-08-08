#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PENDING_AUTHORITIES = {"", "pending", "pending_formal_designation", "not_designated", "none", "null"}
ALLOWED_APPROVAL_STATUSES = {
    "pending_formal_institutional_approval",
    "deferred_until_institutionalization",
    "ready_for_formal_approval",
    "approved",
}
INSTITUTIONAL_STAGES = {"PRODUCTION", "INSTITUTIONAL"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido: {path}")
    return data


def normalized(value: Any) -> str:
    return str(value or "").strip()


def build_readiness(metadata_path: Path) -> dict[str, Any]:
    metadata = load_yaml(metadata_path)
    structural_findings: list[str] = []
    advisory_findings: list[str] = []

    control_id = normalized(metadata.get("control_id"))
    if control_id != "BACEN-01":
        structural_findings.append("invalid_control_id")

    approval_status = normalized(metadata.get("approval_status"))
    if approval_status not in ALLOWED_APPROVAL_STATUSES:
        structural_findings.append("invalid_approval_status")

    lifecycle_stage = normalized(metadata.get("lifecycle_stage")).upper()
    institutional_stage = lifecycle_stage in INSTITUTIONAL_STAGES
    deferred_approval = approval_status == "deferred_until_institutionalization"

    technical_owner = normalized(metadata.get("technical_owner"))
    operational_owner = normalized(metadata.get("operational_owner"))
    if not technical_owner:
        structural_findings.append("technical_owner_missing")
    if not operational_owner:
        structural_findings.append("operational_owner_missing")

    approval_authority = normalized(metadata.get("approval_authority"))
    authority_designated = approval_authority.lower() not in PENDING_AUTHORITIES

    segregation_of_duties_valid: bool | None = None
    if authority_designated:
        segregation_of_duties_valid = approval_authority.casefold() not in {
            technical_owner.casefold(),
            operational_owner.casefold(),
        }
        if not segregation_of_duties_valid:
            structural_findings.append("approval_authority_conflicts_with_policy_owner")
    else:
        advisory_findings.append("formal_approval_authority_pending")

    if approval_status == "approved" and not authority_designated:
        structural_findings.append("approved_without_designated_authority")

    if deferred_approval:
        deferred = metadata.get("deferred_institutional_approval")
        if institutional_stage:
            structural_findings.append("institutional_approval_deferred_in_production_stage")
        if lifecycle_stage == "":
            structural_findings.append("lifecycle_stage_missing_for_deferred_approval")
        if metadata.get("compliance_status") != "technically_implemented":
            structural_findings.append("invalid_compliance_status_for_deferred_approval")
        if metadata.get("institutional_approval_required") is not False:
            structural_findings.append("institutional_approval_must_be_deferred_in_nonproduction")
        if not isinstance(deferred, dict) or deferred.get("enabled") is not True:
            structural_findings.append("deferred_institutional_approval_contract_missing")
        else:
            gate = deferred.get("production_gate")
            if not isinstance(gate, dict) or gate.get("block_production_when_missing") is not True:
                structural_findings.append("deferred_approval_production_gate_missing")
        advisory_findings.append("institutional_approval_deferred_until_promotion")

    structural_checks_passed = not structural_findings
    if deferred_approval and structural_checks_passed:
        readiness_status = "deferred_until_institutionalization"
    elif approval_status == "approved" and authority_designated and structural_checks_passed:
        readiness_status = "authority_validated"
    elif authority_designated and structural_checks_passed:
        readiness_status = "ready_for_formal_approval"
    else:
        readiness_status = "pending_formal_designation"

    if readiness_status == "deferred_until_institutionalization":
        next_stage = "continue_technical_evidence_until_production_gate"
    else:
        next_stage = "designate_independent_approval_authority_and_record_formal_decision"

    return {
        "schema_version": "1.1.0",
        "control_id": "BACEN-01",
        "generated_at": datetime.now(UTC).isoformat(),
        "metadata_path": str(metadata_path),
        "lifecycle_stage": lifecycle_stage,
        "approval_status": approval_status,
        "approval_authority": approval_authority,
        "authority_designated": authority_designated,
        "technical_owner": technical_owner,
        "operational_owner": operational_owner,
        "segregation_of_duties_valid": segregation_of_duties_valid,
        "structural_checks_passed": structural_checks_passed,
        "readiness_status": readiness_status,
        "structural_findings": structural_findings,
        "advisory_findings": advisory_findings,
        "control_status": (
            "implemented"
            if approval_status == "approved" and readiness_status == "authority_validated"
            else "partial"
        ),
        "production_touched": False,
        "next_stage": next_stage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia prontidão da autoridade aprovadora BACEN-01")
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
