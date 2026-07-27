#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = {
    "id",
    "name",
    "service",
    "data_classification",
    "criticality",
    "contract_status",
    "dpa_status",
    "security_review_status",
    "exit_strategy_status",
}

WEIGHTS = {
    "critical": 30,
    "high": 20,
    "medium": 10,
    "low": 0,
}


def load_register(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registro de terceiros deve ser um objeto YAML")
    return payload


def assess_vendor(vendor: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(vendor))
    score = WEIGHTS.get(str(vendor.get("criticality", "")).lower(), 20)
    findings: list[str] = []

    if missing:
        score += 40
        findings.append(f"missing_fields:{','.join(missing)}")
    for field in ("contract_status", "dpa_status", "security_review_status", "exit_strategy_status"):
        if str(vendor.get(field, "")).lower() not in {"approved", "signed", "complete", "validated"}:
            score += 15
            findings.append(f"{field}:{vendor.get(field, 'missing')}")

    score = min(score, 100)
    risk = "critical" if score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
    return {
        "vendor_id": vendor.get("id"),
        "vendor_name": vendor.get("name"),
        "risk_score": score,
        "risk_level": risk,
        "findings": findings,
        "technical_assessment_complete": not missing,
        "legal_signoff_complete": str(vendor.get("dpa_status", "")).lower() in {"signed", "approved"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera avaliação formal BACEN-05 de terceiros")
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    register = load_register(args.register)
    vendors = register.get("vendors") or register.get("third_parties") or []
    if not isinstance(vendors, list) or not vendors:
        raise ValueError("registro deve conter vendors/third_parties não vazio")

    assessments = [assess_vendor(vendor) for vendor in vendors if isinstance(vendor, dict)]
    source_bytes = args.register.read_bytes()
    pending_legal = [item["vendor_id"] for item in assessments if not item["legal_signoff_complete"]]
    high_risk = [item["vendor_id"] for item in assessments if item["risk_level"] in {"high", "critical"}]

    evidence = {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.register),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "vendor_count": len(assessments),
        "technical_assessment_complete": all(item["technical_assessment_complete"] for item in assessments),
        "formal_legal_signoff_complete": not pending_legal,
        "pending_legal_signoff_vendor_ids": pending_legal,
        "high_or_critical_risk_vendor_ids": high_risk,
        "status": "passed" if assessments else "failed",
        "control_maturity": "partial_pending_legal_signoff" if pending_legal else "implemented",
        "production_touched": False,
        "assessments": assessments,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
