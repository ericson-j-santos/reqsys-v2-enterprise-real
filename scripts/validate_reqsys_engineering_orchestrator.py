#!/usr/bin/env python3
"""Validate the ReqSys Engineering Orchestrator v1.0.0 contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_ROUTES = {"planner", "builder", "ci_remediator", "e2e_validator", "human_gate"}
CRITICAL_ROUTE = "human_gate"


def load_structured(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def route_text(text: str, router: dict) -> str:
    normalized = text.casefold()
    routes = {item["id"]: item for item in router["routes"]}
    for route_id in router["execution_order"]:
        route = routes[route_id]
        if any(keyword.casefold() in normalized for keyword in route.get("any_keywords", [])):
            return route_id
    return router["default_route"]


def validate_package(package_dir: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    router = load_structured(package_dir / "router.yaml")
    guardrails = load_structured(package_dir / "guardrails.yaml")

    if router.get("schema_version") != "1.0.0":
        errors.append("router schema_version must be 1.0.0")
    if guardrails.get("schema_version") != "1.0.0":
        errors.append("guardrails schema_version must be 1.0.0")

    route_ids = {item.get("id") for item in router.get("routes", [])}
    missing = sorted(REQUIRED_ROUTES - route_ids)
    if missing:
        errors.append(f"missing routes: {missing}")

    order = router.get("execution_order", [])
    if not order or order[0] != CRITICAL_ROUTE:
        errors.append("human_gate must be first in execution_order")

    routes = {item.get("id"): item for item in router.get("routes", [])}
    human_gate = routes.get(CRITICAL_ROUTE, {})
    if human_gate.get("risk") != "red" or human_gate.get("requires_human_approval") is not True:
        errors.append("human_gate must be red and require human approval")

    critical_actions = set(guardrails.get("critical_actions", []))
    required_critical = {
        "merge", "production_deploy", "production_change", "destructive_database_change",
        "permanent_delete", "force_push", "protected_branch_mutation",
        "administrative_permission_change"
    }
    if not required_critical.issubset(critical_actions):
        errors.append("guardrails missing required critical actions")

    checked_cases = 0
    for filename in ("routing-cases.yaml", "risk-gate-cases.yaml"):
        suite = load_structured(package_dir / "tests" / filename)
        for case in suite.get("cases", []):
            checked_cases += 1
            actual = route_text(case["input"], router)
            if actual != case["expected_route"]:
                errors.append(
                    f"{case['id']}: expected {case['expected_route']}, got {actual}"
                )

    refusal = load_structured(package_dir / "tests" / "refusal-cases.yaml")
    for case in refusal.get("cases", []):
        checked_cases += 1
        if case.get("expected_status") != "blocked":
            errors.append(f"{case.get('id')}: refusal/control case must fail closed")

    report = {
        "contract": "reqsys-engineering-orchestrator",
        "version": "1.0.0",
        "status": "passed" if not errors else "failed",
        "checked_cases": checked_cases,
        "errors": errors,
    }
    return errors, report


def main() -> int:
    parser = argparse.ArgumentParser()
    default_package = (
        Path(__file__).resolve().parents[1]
        / "agents"
        / "reqsys-engineering-orchestrator"
    )
    parser.add_argument("--package-dir", type=Path, default=default_package)
    args = parser.parse_args()

    try:
        errors, report = validate_package(args.package_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        report = {
            "contract": "reqsys-engineering-orchestrator",
            "version": "1.0.0",
            "status": "failed",
            "checked_cases": 0,
            "errors": [str(exc)],
        }
        errors = report["errors"]

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
