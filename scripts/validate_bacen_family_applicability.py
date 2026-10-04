#!/usr/bin/env python3
"""Valida o registro institucional de aplicabilidade da família CMN-4893.

A decisão final é humana e institucional. O validador garante apenas que uma
mudança para `applicable` ou `not_applicable` possua trilha mínima de autoridade,
data, justificativa, referência de aprovação e identificação do escopo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.bacen_derived_status import parse_utc
except ImportError:  # execução direta a partir de scripts/
    from bacen_derived_status import parse_utc

ALLOWED_DECISIONS = {"pending_decision", "applicable", "not_applicable"}
FINAL_DECISIONS = {"applicable", "not_applicable"}
REQUIRED_FINAL_FIELDS = ("decided_by", "decided_at", "rationale", "approval_reference")
REQUIRED_SCOPE_FIELDS = ("legal_entity", "entity_type")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} deve conter um objeto YAML")
    return payload


def validate_family_applicability(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("record") != "bacen_family_applicability_decision":
        errors.append("record deve ser bacen_family_applicability_decision")
    if payload.get("family") != "CMN-4893":
        errors.append("family deve ser CMN-4893")
    if not payload.get("uid"):
        errors.append("uid da decisão é obrigatório")

    decision = str(payload.get("decision") or "").strip()
    if decision not in ALLOWED_DECISIONS:
        errors.append(f"decision inválida: {decision!r}")

    constraints = payload.get("constraints") or {}
    if constraints.get("human_authority_required") is not True:
        errors.append("human_authority_required deve ser true")
    if constraints.get("automatic_inference_allowed") is not False:
        errors.append("automatic_inference_allowed deve ser false")
    if constraints.get("automatic_override_allowed") is not False:
        errors.append("automatic_override_allowed deve ser false")

    if decision == "pending_decision":
        if any(payload.get(field) for field in ("decided_by", "decided_at", "approval_reference")):
            warnings.append(
                "pending_decision contém metadados de decisão parcial; não será tratada como decisão final"
            )
    elif decision in FINAL_DECISIONS:
        for field in REQUIRED_FINAL_FIELDS:
            if not payload.get(field):
                errors.append(f"{decision} exige {field}")

        if payload.get("decided_at"):
            try:
                parse_utc(str(payload["decided_at"]))
            except ValueError as exc:
                errors.append(f"decided_at inválido: {exc}")

        scope = payload.get("institutional_scope") or {}
        for field in REQUIRED_SCOPE_FIELDS:
            if not scope.get(field):
                errors.append(f"{decision} exige institutional_scope.{field}")

        basis = payload.get("regulatory_basis") or []
        if not isinstance(basis, list) or not basis:
            errors.append(f"{decision} exige regulatory_basis não vazio")

    result = "invalid" if errors else "valid_with_pending_decision" if decision == "pending_decision" else "valid"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-bacen-family-applicability-decision",
        "family": payload.get("family"),
        "uid": payload.get("uid"),
        "decision": decision,
        "decision_is_final": decision in FINAL_DECISIONS and not errors,
        "human_authority_required": constraints.get("human_authority_required"),
        "automatic_inference_allowed": constraints.get("automatic_inference_allowed"),
        "automatic_override_allowed": constraints.get("automatic_override_allowed"),
        "errors": errors,
        "warnings": warnings,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--decision-file",
        type=Path,
        default=Path("governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = validate_family_applicability(load_yaml(args.decision_file))
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    return 1 if report["result"] == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
