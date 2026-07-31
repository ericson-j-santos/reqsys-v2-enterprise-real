#!/usr/bin/env python3
"""Consolidate normalized BACEN-02 and BACEN-05 evidence without changing status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"invalid report object: {path}")
    return document


def consolidate(
    mfa_report: dict[str, Any],
    dpa_report: dict[str, Any],
    *,
    mfa_source_ref: str,
    dpa_source_ref: str,
) -> dict[str, Any]:
    mfa_ingestion = mfa_report.get("ingestion") or {}
    dpa_ingestion = dpa_report.get("ingestion") or {}
    dpa_summary = dpa_report.get("summary") or {}

    mfa_integrity_validated = bool(
        isinstance(mfa_ingestion, dict)
        and mfa_ingestion.get("expected_sha256_match") is True
    )
    dpa_integrity_validated = bool(
        isinstance(dpa_ingestion, dict)
        and dpa_ingestion.get("expected_sha256_match") is True
    )
    mfa_ready = bool(
        isinstance(mfa_ingestion, dict)
        and mfa_ingestion.get("accepted") is True
        and mfa_ingestion.get("raw_evidence_persisted") is False
        and mfa_integrity_validated
        and mfa_report.get("structural_checks_passed") is True
        and mfa_report.get("mfa_evidenced") is True
    )
    dpa_ready = bool(
        isinstance(dpa_ingestion, dict)
        and dpa_ingestion.get("accepted") is True
        and dpa_ingestion.get("raw_evidence_persisted") is False
        and dpa_integrity_validated
        and dpa_report.get("result") == "valid"
        and int(dpa_summary.get("validated_records") or 0) >= 1
    )

    controls = {
        "BACEN-02": {
            "evidence_ready": mfa_ready,
            "source_reference": mfa_source_ref,
            "source_integrity_validated_upstream": mfa_integrity_validated,
            "integrity_validation_mode": "upstream_governed_ingestion",
            "human_review_required": True,
        },
        "BACEN-05": {
            "evidence_ready": dpa_ready,
            "source_reference": dpa_source_ref,
            "source_integrity_validated_upstream": dpa_integrity_validated,
            "integrity_validation_mode": "upstream_governed_ingestion",
            "validated_records": int(dpa_summary.get("validated_records") or 0),
            "human_review_required": True,
        },
    }
    ready_count = sum(1 for item in controls.values() if item["evidence_ready"])
    all_ready = ready_count == len(controls)

    return {
        "schema_version": "1.0.0",
        "contract": "bacen-external-evidence-consolidation",
        "decision": "evidence_ready_for_human_review" if all_ready else "blocked",
        "summary": {
            "controls_checked": len(controls),
            "controls_ready": ready_count,
            "controls_blocked": len(controls) - ready_count,
            "all_external_evidence_ready": all_ready,
        },
        "controls": controls,
        "regulatory_status_change_allowed": False,
        "automatic_implementation_claim_allowed": False,
        "human_approval_required": True,
        "raw_external_evidence_persisted": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate normalized BACEN external evidence reports"
    )
    parser.add_argument("--mfa-report", required=True, type=Path)
    parser.add_argument("--dpa-report", required=True, type=Path)
    parser.add_argument("--mfa-source-ref", required=True)
    parser.add_argument("--dpa-source-ref", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        report = consolidate(
            load_report(args.mfa_report),
            load_report(args.dpa_report),
            mfa_source_ref=args.mfa_source_ref,
            dpa_source_ref=args.dpa_source_ref,
        )
    except (ValueError, json.JSONDecodeError, OSError, TypeError) as exc:
        print(f"BACEN external evidence consolidation failed: {type(exc).__name__}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "BACEN external evidence consolidation: "
        f"decision={report['decision']} ready={report['summary']['controls_ready']}/"
        f"{report['summary']['controls_checked']}"
    )
    if args.strict and not report["summary"]["all_external_evidence_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
