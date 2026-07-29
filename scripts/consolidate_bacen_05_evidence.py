#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido: {path}")
    if data.get("control_id") != "BACEN-05":
        raise ValueError(f"control_id inválido em {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_evidence(risk_path: Path, readiness_path: Path, contract_path: Path) -> dict[str, Any]:
    risk = load_json(risk_path)
    readiness = load_json(readiness_path)
    contract = load_json(contract_path)

    vendor_count = int(risk.get("vendor_count", 0))
    registered_vendors = int(readiness.get("summary", {}).get("registered_vendors", 0))
    validated_dpas = int(contract.get("summary", {}).get("validated_records", 0))
    invalid_contract_records = int(contract.get("summary", {}).get("invalid_records", 0))

    structural_errors: list[str] = []
    if vendor_count <= 0:
        structural_errors.append("vendor_risk_assessment_empty")
    if registered_vendors != vendor_count:
        structural_errors.append("vendor_count_mismatch")
    if risk.get("status") != "passed":
        structural_errors.append("vendor_risk_assessment_failed")
    if readiness.get("technical_readiness_passed") is not True:
        structural_errors.append("dpa_readiness_failed")
    if contract.get("result") != "valid" or invalid_contract_records:
        structural_errors.append("dpa_evidence_contract_invalid")

    pending_legal_ids = sorted(set(risk.get("pending_legal_signoff_vendor_ids") or []))
    pending_manifest_ids = sorted(set(readiness.get("pending_vendor_ids") or []))
    legal_pending = bool(pending_legal_ids or pending_manifest_ids)
    full_coverage = vendor_count > 0 and validated_dpas >= vendor_count
    implemented = not structural_errors and full_coverage and not legal_pending

    findings: list[str] = []
    if structural_errors:
        findings.extend(structural_errors)
    if validated_dpas < vendor_count:
        findings.append("validated_dpa_coverage_incomplete")
    if legal_pending:
        findings.append("formal_legal_signoff_pending")
    if risk.get("high_or_critical_risk_vendor_ids"):
        findings.append("high_or_critical_vendor_risk_present")

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "sources": {
            "vendor_risk_assessment": {"path": str(risk_path), "sha256": sha256(risk_path)},
            "vendor_dpa_readiness": {"path": str(readiness_path), "sha256": sha256(readiness_path)},
            "dpa_evidence_contract": {"path": str(contract_path), "sha256": sha256(contract_path)},
        },
        "summary": {
            "registered_vendors": vendor_count,
            "validated_dpas": validated_dpas,
            "validated_dpa_coverage_percent": round((validated_dpas / vendor_count) * 100, 2) if vendor_count else 0.0,
            "pending_legal_signoff_vendors": len(set(pending_legal_ids) | set(pending_manifest_ids)),
            "high_or_critical_risk_vendors": len(risk.get("high_or_critical_risk_vendor_ids") or []),
        },
        "pending_legal_signoff_vendor_ids": sorted(set(pending_legal_ids) | set(pending_manifest_ids)),
        "high_or_critical_risk_vendor_ids": sorted(set(risk.get("high_or_critical_risk_vendor_ids") or [])),
        "technical_consolidation_passed": not structural_errors,
        "formal_requirements_complete": implemented,
        "control_status": "implemented" if implemented else "partial",
        "automatic_blocking": bool(structural_errors),
        "human_action_required": not implemented,
        "findings": findings,
        "production_touched": False,
        "next_stage": "ingest_validated_dpa_references_and_complete_formal_legal_signoff",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida evidências BACEN-05")
    parser.add_argument("--risk", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_evidence(args.risk, args.readiness, args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BACEN-05 consolidated evidence generated")
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
