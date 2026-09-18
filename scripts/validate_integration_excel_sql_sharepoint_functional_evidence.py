#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_E2E_CHECKS = {
    "positive_case",
    "negative_case",
    "idempotency",
    "sql_via_gateway_real_flow",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_functional_evidence(
    candidate: dict[str, Any],
    e2e: dict[str, Any],
    *,
    source_sha: str,
    correlation_id: str,
) -> dict[str, Any]:
    blockers: list[str] = []

    if candidate.get("status") != "resolved":
        blockers.append("candidate_not_resolved")
    if candidate.get("candidate_source") != "original_excel_workbook":
        blockers.append("candidate_source_not_real_excel")
    if candidate.get("real_source") is not True:
        blockers.append("candidate_real_source_not_proven")
    if candidate.get("mocked") is not False or candidate.get("simulated") is not False:
        blockers.append("candidate_mock_or_simulation_detected")
    if candidate.get("synthetic_fixture_used") is not False:
        blockers.append("synthetic_fixture_used")
    if candidate.get("source_sha") != source_sha:
        blockers.append("candidate_source_sha_mismatch")
    if candidate.get("correlation_id") != correlation_id:
        blockers.append("candidate_correlation_mismatch")

    if e2e.get("status") != "passed":
        blockers.append("e2e_not_passed")
    if e2e.get("real") is not True or e2e.get("mocked") is not False or e2e.get("simulated") is not False:
        blockers.append("e2e_not_real")
    if e2e.get("source_sha") != source_sha:
        blockers.append("e2e_source_sha_mismatch")
    if e2e.get("correlation_id") != correlation_id:
        blockers.append("e2e_correlation_mismatch")
    if e2e.get("sql_validation_mode") != "power_platform_gateway":
        blockers.append("e2e_not_gateway_mode")

    positive = e2e.get("positive") or {}
    identifier = str(positive.get("identifier") or "")
    expected_digest = str(candidate.get("selected_identifier_sha256") or "")
    if not identifier or not expected_digest or digest(identifier) != expected_digest:
        blockers.append("positive_identifier_not_bound_to_real_candidate")

    checks = e2e.get("checks") or {}
    for name in sorted(REQUIRED_E2E_CHECKS):
        if checks.get(name) != "passed":
            blockers.append(f"e2e_check_not_passed:{name}")

    if positive.get("independent_read") != "passed":
        blockers.append("positive_independent_read_missing")
    negative = e2e.get("negative") or {}
    if negative.get("independent_read") != "passed":
        blockers.append("negative_independent_read_missing")
    idempotency = e2e.get("idempotency") or {}
    if idempotency.get("independent_read") != "passed":
        blockers.append("idempotency_independent_read_missing")
    if idempotency.get("same_item_id") is not True:
        blockers.append("idempotency_same_item_not_proven")

    cleanup = e2e.get("cleanup") or {}
    if cleanup.get("flow_stopped") is not True:
        blockers.append("cleanup_flow_not_stopped")
    if cleanup.get("workbook_restored") is not True:
        blockers.append("cleanup_workbook_not_restored")
    if cleanup.get("sharepoint_item_removed") is not True:
        blockers.append("cleanup_sharepoint_item_not_removed")

    return {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_functional_evidence",
        "source_sha": source_sha,
        "correlation_id": correlation_id,
        "functional_evidence": not blockers,
        "candidate_source": candidate.get("candidate_source"),
        "synthetic_fixture_used": candidate.get("synthetic_fixture_used"),
        "selected_identifier_sha256": expected_digest or None,
        "e2e_status": e2e.get("status"),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate final de evidência funcional Excel -> SQL -> SharePoint")
    parser.add_argument("--candidate-evidence", type=Path, required=True)
    parser.add_argument("--e2e-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    candidate = json.loads(args.candidate_evidence.read_text(encoding="utf-8"))
    e2e = json.loads(args.e2e_evidence.read_text(encoding="utf-8"))
    result = validate_functional_evidence(
        candidate,
        e2e,
        source_sha=args.source_sha,
        correlation_id=args.correlation_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"functional_evidence": result["functional_evidence"], "blockers": result["blockers"]}, ensure_ascii=False))
    if args.strict and not result["functional_evidence"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
