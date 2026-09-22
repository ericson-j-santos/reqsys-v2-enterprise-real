#!/usr/bin/env python3
"""Executa o Gate 2 usando o registro institucional autoritativo de aplicabilidade."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.validate_bacen_family_applicability import (
        load_yaml as load_applicability_yaml,
        validate_family_applicability,
    )
    from scripts.validate_bacen_production_readiness import (
        PRODUCTION_STAGE,
        evaluate_readiness,
        load_yaml,
    )
except ImportError:  # execução direta a partir de scripts/
    from validate_bacen_family_applicability import (
        load_yaml as load_applicability_yaml,
        validate_family_applicability,
    )
    from validate_bacen_production_readiness import PRODUCTION_STAGE, evaluate_readiness, load_yaml

DEFAULT_DECISION_FILE = Path("governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml")


def authoritative_applicability(payload: dict) -> dict:
    validation = validate_family_applicability(payload)
    if validation["result"] == "invalid":
        raise ValueError("registro institucional de aplicabilidade inválido: " + "; ".join(validation["errors"]))
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
    parser.add_argument("--target-stage", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    decision_payload = load_applicability_yaml(args.family_applicability)
    applicability = authoritative_applicability(decision_payload)

    baseline_v2 = load_yaml(args.baseline_v2)
    baseline_v2["applicability"] = applicability

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
    report["family_applicability_source"] = str(args.family_applicability)
    report["family_applicability_record_uid"] = applicability.get("record_uid")
    report["family_applicability_approval_reference"] = applicability.get("approval_reference")
    report["family_applicability_decided_by"] = applicability.get("decided_by")
    report["family_applicability_decided_at"] = applicability.get("decided_at")

    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")

    if args.enforce and report["target_stage"] == PRODUCTION_STAGE and report["decision"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
