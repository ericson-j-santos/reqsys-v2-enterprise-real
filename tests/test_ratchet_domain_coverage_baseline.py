from __future__ import annotations

import pytest

from scripts.ratchet_domain_coverage_baseline import ratchet


def policy() -> dict:
    return {
        "mode": "regression_gate",
        "domains": {
            "core": {"target_percent": 80.0},
            "services": {"target_percent": 75.0},
        },
        "baseline": {"core": 70.0, "services": 60.0},
    }


def report(core: float, services: float) -> dict:
    return {
        "status": "passed",
        "domains": {
            "core": {"coverage_percent": core, "statements": 100, "matched_files": ["app/core/a.py"]},
            "services": {"coverage_percent": services, "statements": 100, "matched_files": ["app/services/b.py"]},
        },
    }


def test_promotes_only_gain_at_or_above_threshold() -> None:
    updated, evidence = ratchet(report(70.5, 60.2), policy(), minimum_gain=0.5)

    assert updated["baseline"] == {"core": 70.5, "services": 60.0}
    assert set(evidence["promoted"]) == {"core"}
    assert evidence["unchanged"]["services"]["reason"] == "gain_below_threshold"


def test_never_promotes_regression() -> None:
    updated, evidence = ratchet(report(69.0, 61.0), policy(), minimum_gain=0.5)

    assert updated["baseline"]["core"] == 70.0
    assert evidence["unchanged"]["core"]["reason"] == "regression_not_promoted"
    assert updated["baseline"]["services"] == 61.0


def test_requires_initial_baseline() -> None:
    current = policy()
    current["baseline"] = {}

    with pytest.raises(ValueError, match="baseline inicial"):
        ratchet(report(70.5, 60.5), current)
