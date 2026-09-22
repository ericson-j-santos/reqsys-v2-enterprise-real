from __future__ import annotations

import pytest

from scripts.propose_domain_coverage_baseline import build_proposal


def valid_report() -> dict:
    return {
        "status": "baseline_required",
        "domains": {
            "core": {
                "coverage_percent": 72.5,
                "target_percent": 80.0,
                "statements": 200,
                "matched_files": ["app/core/a.py"],
            },
            "services": {
                "coverage_percent": 64.0,
                "target_percent": 75.0,
                "statements": 100,
                "matched_files": ["app/services/b.py"],
            },
        },
    }


def policy() -> dict:
    return {
        "schema_version": "1.0.0",
        "mode": "record_then_regression",
        "domains": {
            "core": {"paths": ["backend/app/core/"], "target_percent": 80.0},
            "services": {"paths": ["backend/app/services/"], "target_percent": 75.0},
        },
        "baseline": {},
    }


def test_build_proposal_activates_regression_gate() -> None:
    updated, diff = build_proposal(valid_report(), policy())

    assert updated["mode"] == "regression_gate"
    assert updated["baseline"] == {"core": 72.5, "services": 64.0}
    assert diff["requires_human_approval"] is True


def test_build_proposal_rejects_domain_without_evidence() -> None:
    report = valid_report()
    report["domains"]["core"]["matched_files"] = []

    with pytest.raises(ValueError, match="Domínio sem evidência válida"):
        build_proposal(report, policy())


def test_build_proposal_reports_regression_and_improvement() -> None:
    current_policy = policy()
    current_policy["baseline"] = {"core": 75.0, "services": 60.0}
    report = valid_report()
    report["status"] = "passed"

    _, diff = build_proposal(report, current_policy)

    assert diff["domains"]["core"]["regression"] is True
    assert diff["domains"]["services"]["improvement"] is True
