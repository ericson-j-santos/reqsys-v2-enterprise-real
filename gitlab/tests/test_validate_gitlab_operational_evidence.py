from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate_gitlab_operational_evidence.py"
SPEC = importlib.util.spec_from_file_location("gitlab_operational_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_evidence() -> dict:
    return {
        "project": {"approvals_before_merge": 1},
        "pipeline": {"id": 123, "status": "running"},
        "jobs": [
            {"name": name, "status": "success"}
            for name in sorted(MODULE.REQUIRED_SCANNER_JOBS)
        ],
        "protected_branch": {
            "name": "main",
            "push_access_levels": [{"access_level": 40}],
            "merge_access_levels": [{"access_level": 40}],
        },
        "approval_rules": [{"name": "default", "approvals_required": 1}],
        "deployments": [{"id": 1, "status": "success"}],
        "environment": "staging",
    }


def test_gate_passes_with_complete_operational_evidence() -> None:
    ok, checks = MODULE.evaluate(valid_evidence())
    assert ok is True
    assert all(check["passed"] for check in checks)


def test_gate_fails_when_scanner_and_deploy_evidence_are_absent() -> None:
    evidence = valid_evidence()
    evidence["jobs"] = []
    evidence["deployments"] = []

    ok, checks = MODULE.evaluate(evidence)
    failed = {check["name"] for check in checks if not check["passed"]}

    assert ok is False
    assert failed == {"security_scanners", "deployment_evidence"}


def test_gate_fails_without_branch_protection_or_approval() -> None:
    evidence = valid_evidence()
    evidence["protected_branch"] = {}
    evidence["approval_rules"] = []
    evidence["project"] = {"approvals_before_merge": 0}

    ok, checks = MODULE.evaluate(evidence)
    failed = {check["name"] for check in checks if not check["passed"]}

    assert ok is False
    assert failed == {"default_branch_protection", "merge_approvals"}
