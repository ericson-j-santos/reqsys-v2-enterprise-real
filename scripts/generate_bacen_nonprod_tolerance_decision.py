#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

VALID_SCOPES = {"pull_request", "dev", "stg", "prod"}
VALID_STATUSES = {"implemented", "partial", "gap"}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def parse_policy_date(value: Any, field: str, findings: list[str]) -> date | None:
    raw = str(value or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        findings.append(f"invalid_policy_date:{field}")
        return None


def build_decision(
    matrix_path: Path,
    policy_path: Path,
    scope: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if scope not in VALID_SCOPES:
        raise ValueError(f"Escopo inválido: {scope}")

    matrix = load_yaml(matrix_path)
    policy = load_yaml(policy_path)
    controls = matrix.get("controls") or []
    if not isinstance(controls, list):
        raise ValueError("controls deve ser uma lista")

    allowed_scopes = set(policy.get("allowed_scopes") or [])
    blocked_scopes = set(policy.get("blocked_scopes") or [])
    allowed_statuses = set(policy.get("allowed_control_statuses") or [])
    always_block_statuses = set(policy.get("always_block_statuses") or [])
    review_window_days = int(policy.get("maximum_review_window_days") or 0)
    activation = policy.get("activation") or {}
    if not isinstance(activation, dict):
        activation = {}

    structural_findings: list[str] = []
    tolerated_controls: list[str] = []
    blocking_controls: list[str] = []
    evaluated: list[dict[str, Any]] = []

    valid_from = parse_policy_date(activation.get("valid_from"), "valid_from", structural_findings)
    valid_until = parse_policy_date(
        activation.get("valid_until"), "valid_until", structural_findings
    )
    review_owner_role = str(activation.get("review_owner_role") or "").strip()
    explicit_renewal = activation.get("renewal_requires_explicit_policy_change") is True

    if not allowed_scopes <= VALID_SCOPES:
        structural_findings.append("policy_contains_invalid_allowed_scope")
    if not blocked_scopes <= VALID_SCOPES:
        structural_findings.append("policy_contains_invalid_blocked_scope")
    if allowed_scopes & blocked_scopes:
        structural_findings.append("policy_scope_overlap")
    if not allowed_statuses <= VALID_STATUSES:
        structural_findings.append("policy_contains_invalid_allowed_status")
    if not always_block_statuses <= VALID_STATUSES:
        structural_findings.append("policy_contains_invalid_block_status")
    if review_window_days < 1 or review_window_days > 90:
        structural_findings.append("invalid_review_window_days")
    if not review_owner_role:
        structural_findings.append("review_owner_role_missing")
    if not explicit_renewal:
        structural_findings.append("explicit_renewal_not_required")
    if valid_from and valid_until:
        if valid_until < valid_from:
            structural_findings.append("policy_validity_range_inverted")
        if (valid_until - valid_from).days > review_window_days:
            structural_findings.append("policy_validity_exceeds_review_window")

    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    evaluation_date = generated_at.astimezone(UTC).date()
    policy_active = bool(
        valid_from
        and valid_until
        and valid_from <= evaluation_date <= valid_until
        and not structural_findings
    )
    if valid_from and evaluation_date < valid_from:
        structural_findings.append("temporary_tolerance_not_active_yet")
    if valid_until and evaluation_date > valid_until:
        structural_findings.append("temporary_tolerance_expired")

    for control in controls:
        if not isinstance(control, dict):
            structural_findings.append("invalid_control_entry")
            continue

        control_id = str(control.get("id") or "").strip()
        status = str(control.get("status") or "").strip().lower()
        production_touched = bool(control.get("production_touched", False))

        if not control_id:
            structural_findings.append("control_id_missing")
            continue
        if status not in VALID_STATUSES:
            structural_findings.append(f"invalid_control_status:{control_id}")
            blocking_controls.append(control_id)
        elif status in always_block_statuses:
            blocking_controls.append(control_id)
        elif production_touched:
            blocking_controls.append(control_id)
        elif scope in blocked_scopes and status != "implemented":
            blocking_controls.append(control_id)
        elif policy_active and scope in allowed_scopes and status in allowed_statuses:
            if status == "partial":
                tolerated_controls.append(control_id)
        elif status != "implemented":
            blocking_controls.append(control_id)

        evaluated.append(
            {
                "control_id": control_id,
                "status": status,
                "criticality": control.get("criticality"),
                "production_touched": production_touched,
                "human_action_pending": status != "implemented",
            }
        )

    automatic_blocking = bool(structural_findings or blocking_controls)
    temporary_tolerance_applied = bool(tolerated_controls) and not automatic_blocking

    return {
        "schema_version": "1.1.0",
        "generated_at": generated_at.isoformat(),
        "scope": scope,
        "mode": "temporary_nonprod_tolerance",
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "policy_path": str(policy_path),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "decision": "allow" if not automatic_blocking else "block",
        "temporary_tolerance_applied": temporary_tolerance_applied,
        "tolerated_controls": sorted(set(tolerated_controls)),
        "blocking_controls": sorted(set(blocking_controls)),
        "structural_findings": sorted(set(structural_findings)),
        "evaluated_controls": evaluated,
        "policy_active": policy_active,
        "valid_from": str(valid_from) if valid_from else None,
        "valid_until": str(valid_until) if valid_until else None,
        "review_deadline": str(valid_until) if valid_until else None,
        "review_owner_role": review_owner_role or None,
        "renewal_requires_explicit_policy_change": explicit_renewal,
        "production_deployment_allowed": scope == "prod" and not automatic_blocking,
        "preserved_control_status": True,
        "human_action_required": bool(tolerated_controls or blocking_controls),
        "production_touched": False,
        "next_stage": "complete_real_human_approvals_and_remove_temporary_tolerance",
        "automatic_blocking": automatic_blocking,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Decide tolerância temporária BACEN por ambiente")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--scope", choices=sorted(VALID_SCOPES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_decision(args.matrix, args.policy, args.scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "scope": evidence["scope"],
                "decision": evidence["decision"],
                "policy_active": evidence["policy_active"],
                "valid_until": evidence["valid_until"],
                "tolerated_controls": evidence["tolerated_controls"],
                "blocking_controls": evidence["blocking_controls"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
