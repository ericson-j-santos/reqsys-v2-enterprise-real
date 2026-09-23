#!/usr/bin/env python3
"""Executa o Gate 2 usando o registro institucional autoritativo de aplicabilidade."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.validate_bacen_family_applicability import (
        load_yaml as load_applicability_yaml,
        validate_family_applicability,
    )
    from scripts.validate_bacen_production_readiness import (
        PRODUCTION_STAGE,
        evaluate_readiness,
        load_yaml,
        normalize_stage,
    )
except ImportError:  # execução direta a partir de scripts/
    from validate_bacen_family_applicability import (
        load_yaml as load_applicability_yaml,
        validate_family_applicability,
    )
    from validate_bacen_production_readiness import (
        PRODUCTION_STAGE,
        evaluate_readiness,
        load_yaml,
        normalize_stage,
    )

DEFAULT_DECISION_FILE = Path("governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml")
DEFAULT_PRODUCTION_EXCEPTION_FILE = Path(
    "governance/bacen/exceptions/"
    "CMN4893-SCOPE-DATA-PROD-TECHNICAL-EXCEPTION-2026-09-22.yaml"
)
EXPECTED_EXCEPTION_ID = "REQSYS-BACEN-CMN4893-SCOPE-DATA-PROD-EXCEPTION-2026-09-22"
EXPECTED_DEFERRED_FIELDS = [
    "institutional_scope.legal_entity",
    "institutional_scope.entity_type",
]
EXPECTED_BLOCKER_CODES = ["family_applicability_pending"]


def authoritative_applicability(payload: dict) -> dict:
    validation = validate_family_applicability(payload)
    if validation["result"] == "invalid":
        raise ValueError(
            "registro institucional de aplicabilidade inválido: "
            + "; ".join(validation["errors"])
        )
    return {
        "family": payload.get("family"),
        "decision": payload.get("decision"),
        "decided_by": payload.get("decided_by"),
        "decided_at": payload.get("decided_at"),
        "rationale": payload.get("rationale"),
        "approval_reference": payload.get("approval_reference"),
        "institutional_scope": payload.get("institutional_scope") or {},
        "record_uid": payload.get("uid"),
    }


def _date(value: Any, field: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"invalid_date:{field}")
        return None


def _as_of_date(value: str) -> date:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).date()


def validate_temporary_production_exception(
    payload: dict[str, Any],
    *,
    authoritative: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    errors: list[str] = []

    if payload.get("record") != "bacen_temporary_production_scope_exception":
        errors.append("invalid_record")
    if payload.get("exception_id") != EXPECTED_EXCEPTION_ID:
        errors.append("invalid_exception_id")
    if payload.get("status") != "active":
        errors.append("exception_not_active")

    subject = payload.get("subject") or {}
    if subject.get("family") != "CMN-4893":
        errors.append("invalid_family")
    if subject.get("issue") != 1505:
        errors.append("invalid_issue")
    if subject.get("authoritative_decision_file") != str(DEFAULT_DECISION_FILE):
        errors.append("invalid_authoritative_decision_file")

    approval = payload.get("approval") or {}
    if not approval.get("approved_by"):
        errors.append("approved_by_missing")
    if not approval.get("approval_reference"):
        errors.append("approval_reference_missing")
    if approval.get("decision_intent") != "applicable":
        errors.append("decision_intent_must_be_applicable")

    if payload.get("temporarily_deferred_fields") != EXPECTED_DEFERRED_FIELDS:
        errors.append("invalid_deferred_fields")
    if payload.get("allowed_scopes") != ["prod"]:
        errors.append("invalid_allowed_scopes")
    if payload.get("covered_blocker_codes") != EXPECTED_BLOCKER_CODES:
        errors.append("invalid_covered_blocker_codes")

    constraints = payload.get("constraints") or {}
    required_constraints = {
        "technical_production_deployment_may_be_evaluated": True,
        "regulatory_finality_allowed": False,
        "regulatory_compliance_claim_allowed": False,
        "fabricated_values_allowed": False,
        "automatic_inference_allowed": False,
        "authoritative_decision_must_remain": "pending_decision",
        "no_other_gate_bypass_allowed": True,
    }
    for field, expected in required_constraints.items():
        if constraints.get(field) != expected:
            errors.append(f"invalid_constraint:{field}")

    expected_unknowns = [
        "institutional_scope.rsfn_connection",
        "institutional_scope.pix_participant",
        "institutional_scope.str_participant",
        "institutional_scope.smf_scope",
    ]
    if constraints.get("preserve_conditional_unknowns") != expected_unknowns:
        errors.append("invalid_preserve_conditional_unknowns")

    validity = payload.get("validity") or {}
    valid_from = _date(validity.get("valid_from"), "valid_from", errors)
    valid_until = _date(validity.get("valid_until"), "valid_until", errors)
    if validity.get("renewal_requires_explicit_human_approval") is not True:
        errors.append("explicit_human_renewal_required")
    if validity.get("expires_fail_closed") is not True:
        errors.append("expiry_must_fail_closed")
    if valid_from and valid_until and valid_until < valid_from:
        errors.append("validity_range_inverted")

    audit = payload.get("audit") or {}
    if audit.get("replaces_regulatory_evidence") is not False:
        errors.append("must_not_replace_regulatory_evidence")
    if audit.get("compliance_claim_allowed") is not False:
        errors.append("compliance_claim_must_be_false")

    authoritative_decision = str(authoritative.get("decision") or "")
    if authoritative_decision != "pending_decision":
        return {
            "present": True,
            "active": False,
            "applied": False,
            "reason": "authoritative_decision_is_final",
            "errors": errors,
            "exception_id": payload.get("exception_id"),
            "valid_until": str(valid_until) if valid_until else None,
            "approval_reference": approval.get("approval_reference"),
        }

    evaluation_date = _as_of_date(as_of)
    active_window = bool(
        valid_from
        and valid_until
        and valid_from <= evaluation_date <= valid_until
    )
    if valid_from and evaluation_date < valid_from:
        errors.append("exception_not_active_yet")
    if valid_until and evaluation_date > valid_until:
        errors.append("exception_expired")

    active = active_window and not errors
    return {
        "present": True,
        "active": active,
        "applied": False,
        "reason": "active" if active else "invalid_or_expired",
        "errors": errors,
        "exception_id": payload.get("exception_id"),
        "valid_until": str(valid_until) if valid_until else None,
        "approval_reference": approval.get("approval_reference"),
    }


def effective_applicability_for_target(
    authoritative: dict[str, Any],
    exception_report: dict[str, Any],
    *,
    target_stage: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    effective = dict(authoritative)
    resolved_exception = dict(exception_report)
    resolved_exception["applied"] = False
    if (
        normalize_stage(target_stage) == PRODUCTION_STAGE
        and authoritative.get("decision") == "pending_decision"
        and resolved_exception.get("active") is True
    ):
        effective["decision"] = "applicable"
        resolved_exception["applied"] = True
    return effective, resolved_exception


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-v2", type=Path, required=True)
    parser.add_argument("--base-obligations", type=Path, required=True)
    parser.add_argument("--extended-obligations", type=Path, required=True)
    parser.add_argument("--evidence-registry", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--family-applicability", type=Path, default=DEFAULT_DECISION_FILE)
    parser.add_argument("--temporary-production-exception", type=Path)
    parser.add_argument("--target-stage", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    decision_payload = load_applicability_yaml(args.family_applicability)
    authoritative = authoritative_applicability(decision_payload)
    target_stage = normalize_stage(args.target_stage)

    exception_report: dict[str, Any] = {
        "present": False,
        "active": False,
        "applied": False,
        "reason": "not_provided",
        "errors": [],
        "exception_id": None,
        "valid_until": None,
        "approval_reference": None,
    }
    if args.temporary_production_exception:
        exception_payload = load_yaml(args.temporary_production_exception)
        exception_report = validate_temporary_production_exception(
            exception_payload,
            authoritative=authoritative,
            as_of=args.as_of,
        )
    effective, exception_report = effective_applicability_for_target(
        authoritative,
        exception_report,
        target_stage=target_stage,
    )

    baseline_v2 = load_yaml(args.baseline_v2)
    baseline_v2["applicability"] = effective

    report = evaluate_readiness(
        baseline_v2=baseline_v2,
        base_obligations=load_yaml(args.base_obligations),
        extended_obligations=load_yaml(args.extended_obligations),
        evidence_registry=load_yaml(args.evidence_registry),
        policy=load_yaml(args.policy),
        matrix=load_yaml(args.matrix),
        reconciliation=load_yaml(args.reconciliation),
        target_stage=args.target_stage,
        as_of=args.as_of,
    )

    # A exceção muda somente a decisão efetiva usada para avaliação técnica.
    # O estado institucional autoritativo permanece explicitamente preservado.
    report["family_applicability_source"] = str(args.family_applicability)
    report["family_applicability_record_uid"] = authoritative.get("record_uid")
    report["family_applicability_approval_reference"] = authoritative.get(
        "approval_reference"
    )
    report["family_applicability_decided_by"] = authoritative.get("decided_by")
    report["family_applicability_decided_at"] = authoritative.get("decided_at")
    report["family_applicability_authoritative_decision"] = authoritative.get(
        "decision"
    )
    report["family_applicability_effective_decision"] = effective.get("decision")
    report["family_applicability_decision"] = authoritative.get("decision")
    report["temporary_production_exception_present"] = exception_report["present"]
    report["temporary_production_exception_active"] = exception_report["active"]
    report["temporary_production_exception_applied"] = exception_report["applied"]
    report["temporary_production_exception_id"] = exception_report["exception_id"]
    report["temporary_production_exception_valid_until"] = exception_report[
        "valid_until"
    ]
    report["temporary_production_exception_approval_reference"] = exception_report[
        "approval_reference"
    ]
    report["temporary_production_exception_errors"] = exception_report["errors"]
    report["regulatory_finality_allowed"] = False
    report["regulatory_compliance_claim_allowed"] = False

    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")

    if (
        args.enforce
        and report["target_stage"] == PRODUCTION_STAGE
        and report["decision"] == "blocked"
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
