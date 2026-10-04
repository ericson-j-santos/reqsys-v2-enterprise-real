#!/usr/bin/env python3
"""Valida o bloqueio formal BACEN antes de qualquer promoção para produção."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

PRODUCTION_STAGE = "PRODUCTION"
REQUIRED_PRODUCTION_CONTROLS = ("BACEN-01", "BACEN-08")
DEFERRED_MARKER = "deferred"

DEFERRED_MATRIX_KEYS = (
    "decision_status",
    "approval_status",
    "institutional_governance_status",
    "executive_designation_status",
    "report_signoff_status",
    "evidence_stage",
    "next_stage",
)

REQUIRED_FORMAL_FIELDS = {
    "BACEN-01": (
        "formal_approval_authority",
        "signed_attestation_reference",
        "institutional_approval_date",
    ),
    "BACEN-08": (
        "formal_executive_designation",
        "designated_by",
        "formal_report_signoff",
        "report_signed_by",
        "report_signed_at",
    ),
}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} deve conter um objeto YAML")
    return payload


def find_matrix_control(matrix: dict[str, Any], control_id: str) -> dict[str, Any]:
    controls = matrix.get("controls")
    if not isinstance(controls, list):
        raise ValueError("Matriz BACEN inválida: controls deve ser lista")
    matches = [item for item in controls if isinstance(item, dict) and item.get("id") == control_id]
    if len(matches) != 1:
        raise ValueError(f"Controle {control_id} não encontrado de forma única na matriz")
    return matches[0]


def find_reconciliation_control(reconciliation: dict[str, Any], control_id: str) -> dict[str, Any]:
    controls = reconciliation.get("controls")
    if not isinstance(controls, list):
        raise ValueError("Reconciliação BACEN inválida: controls deve ser lista")
    matches = [
        item for item in controls if isinstance(item, dict) and item.get("control_id") == control_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Controle {control_id} não encontrado de forma única na reconciliação")
    return matches[0]


def has_deferred_value(control: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    deferred: list[str] = []
    for key in keys:
        value = control.get(key)
        if value is not None and DEFERRED_MARKER in str(value).lower():
            deferred.append(key)
    return deferred


def normalize_stage(value: str) -> str:
    return str(value or "").strip().upper()


def evaluate_gate(
    matrix: dict[str, Any],
    reconciliation: dict[str, Any],
    *,
    target_stage: str,
) -> dict[str, Any]:
    target = normalize_stage(target_stage)
    production_target = target == PRODUCTION_STAGE
    blockers: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    for control_id in REQUIRED_PRODUCTION_CONTROLS:
        matrix_control = find_matrix_control(matrix, control_id)
        reconciliation_control = find_reconciliation_control(reconciliation, control_id)
        matrix_deferred_keys = has_deferred_value(matrix_control, DEFERRED_MATRIX_KEYS)
        deferred_requirements = list(reconciliation_control.get("deferred_requirements") or [])
        production_gate = reconciliation_control.get("production_gate") or {}
        status = str(matrix_control.get("status") or "").strip()

        item = {
            "control_id": control_id,
            "matrix_status": status,
            "matrix_deferred_keys": matrix_deferred_keys,
            "deferred_requirements": deferred_requirements,
            "production_gate_required": bool(production_gate.get("required")),
            "block_when_deferred_requirements_missing": bool(
                production_gate.get("block_when_deferred_requirements_missing")
            ),
        }

        if not production_target:
            observations.append({**item, "decision": "deferred_allowed_before_production"})
            continue

        reasons: list[str] = []
        if status != "implemented":
            reasons.append(f"status atual é {status or 'ausente'}, esperado implemented")
        if matrix_deferred_keys:
            reasons.append("campos da matriz ainda indicam diferimento formal")
        if deferred_requirements:
            required = ", ".join(str(value) for value in deferred_requirements)
            reasons.append(f"requisitos formais diferidos ausentes: {required}")
        if production_gate.get("required") is not True:
            reasons.append("production_gate.required não está verdadeiro")
        if production_gate.get("block_when_deferred_requirements_missing") is not True:
            reasons.append("production_gate.block_when_deferred_requirements_missing não está verdadeiro")

        if reasons:
            blockers.append({**item, "reasons": reasons})
        else:
            observations.append({**item, "decision": "production_ready"})

    decision = "blocked" if blockers else "allowed"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-bacen-production-formal-gate",
        "target_stage": target,
        "required_controls": list(REQUIRED_PRODUCTION_CONTROLS),
        "decision": decision,
        "production_touched": False,
        "automatic_override_allowed": False,
        "blockers": blockers,
        "observations": observations,
        "required_formal_fields": REQUIRED_FORMAL_FIELDS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--target-stage", default=PRODUCTION_STAGE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--expect-block",
        action="store_true",
        help="Falha se a promoção para produção não estiver bloqueada.",
    )
    args = parser.parse_args()

    report = evaluate_gate(
        load_yaml(args.matrix),
        load_yaml(args.reconciliation),
        target_stage=args.target_stage,
    )
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")

    blocked = report["decision"] == "blocked"
    if args.expect_block:
        return 0 if blocked else 1
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
