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

    structural_checks_passed = (
        cycle_days == 90
        and not missing_dimensions
        and not missing_roles
        and not review_overdue
        and document.get("production_touched") is False
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

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-02",
        "generated_at": datetime.now(UTC).isoformat(),
        "register_path": str(register_path),
        "register_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "review_cycle_days": cycle_days,
        "review_status": review_status,
        "formal_review_completed": formal_review_completed,
        "reviewed_at": str(reviewed_at) if reviewed_at else None,
        "next_review_due_at": str(next_review_due_at) if next_review_due_at else None,
        "review_overdue": review_overdue,
        "mfa_evidenced": mfa_evidenced,
        "missing_review_dimensions": missing_dimensions,
        "missing_privileged_roles": missing_roles,
        "structural_checks_passed": structural_checks_passed,
        "control_status": "implemented" if formal_review_completed and mfa_evidenced else "partial",
        "findings": findings,
        "human_action_required": not formal_review_completed,
        "external_evidence_required": not mfa_evidenced,
        "automatic_blocking": False,
        "production_touched": False,
        "next_stage": document.get("next_stage"),
    }


def build_log_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """Retorna somente campos operacionais permitidos para logs do CI."""
    return {
        "control_id": evidence["control_id"],
        "control_status": evidence["control_status"],
        "structural_checks_passed": evidence["structural_checks_passed"],
        "formal_review_completed": evidence["formal_review_completed"],
        "mfa_evidenced": evidence["mfa_evidenced"],
        "review_overdue": evidence["review_overdue"],
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
    return 0 if evidence["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
