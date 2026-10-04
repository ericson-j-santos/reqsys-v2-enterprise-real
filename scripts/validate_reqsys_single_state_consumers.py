#!/usr/bin/env python3
"""Validate canonical ReqSys Single State consumer readiness.

This validator is deterministic, offline and report-only. It verifies that the
canonical contract exposes every section declared by Governance, Runtime and
Analytics without changing production or promotion decisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_STATE = Path("docs/ops-dashboard/data/reqsys-single-state.json")
DEFAULT_REPORT = Path("artifacts/reqsys-single-state-consumer-readiness/report.json")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    consumers = contract.get("consumers") or {}
    state = contract.get("state") or {}
    results: dict[str, Any] = {}

    for consumer_name, consumer_contract in consumers.items():
        required = consumer_contract.get("required_sections") or []
        missing = [section for section in required if section not in state]
        empty = [section for section in required if section in state and state[section] in ({}, [], None, "")]
        results[consumer_name] = {
            "ready": not missing and not empty,
            "required_sections": required,
            "missing_sections": missing,
            "empty_sections": empty,
            "purpose": consumer_contract.get("purpose", ""),
        }

    expected_consumers = {"governance", "runtime", "analytics"}
    absent_consumers = sorted(expected_consumers - set(consumers))
    ready_count = sum(1 for item in results.values() if item["ready"])
    total_count = len(expected_consumers)
    all_ready = not absent_consumers and ready_count == total_count

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state-consumer-readiness",
        "mode": "report_only",
        "production_blocker": False,
        "automatic_promotion_allowed": False,
        "source_contract": contract.get("contract", "unknown"),
        "source_schema_version": contract.get("schema_version", "unknown"),
        "status": "READY" if all_ready else "EVIDENCE_INCOMPLETE",
        "readiness_percent": round((ready_count / total_count) * 100, 2),
        "ready_consumers": ready_count,
        "total_consumers": total_count,
        "absent_consumers": absent_consumers,
        "consumers": results,
        "next_safe_increment": (
            "switch governed consumers to the canonical contract"
            if all_ready
            else "complete missing or empty canonical state sections before consumer migration"
        ),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ReqSys Single State consumers")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    report = validate_contract(load_json(args.state))
    write_json(args.report, report)
    print(json.dumps({"status": report["status"], "readiness_percent": report["readiness_percent"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
