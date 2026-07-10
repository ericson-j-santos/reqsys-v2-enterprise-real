from __future__ import annotations

from scripts.evaluate_domain_coverage import evaluate


def coverage_payload(core_percent: float, service_percent: float) -> dict:
    return {
        "files": {
            "backend/app/core/a.py": {
                "summary": {"covered_lines": int(core_percent), "num_statements": 100}
            },
            "backend/app/services/b.py": {
                "summary": {"covered_lines": int(service_percent), "num_statements": 100}
            },
        }
    }


def policy_payload(baseline: dict | None = None) -> dict:
    return {
        "mode": "record_then_regression",
        "allowed_regression_percentage_points": 0.0,
        "domains": {
            "core": {"paths": ["backend/app/core/"], "target_percent": 80},
            "services": {"paths": ["backend/app/services/"], "target_percent": 75},
        },
        "baseline": baseline or {},
    }


def test_first_run_records_without_blocking() -> None:
    report = evaluate(coverage_payload(70, 60), policy_payload())

    assert report["status"] == "baseline_required"
    assert report["regressions"] == []
    assert report["domains"]["core"]["coverage_percent"] == 70.0


def test_regression_fails_when_below_committed_baseline() -> None:
    report = evaluate(
        coverage_payload(69, 60),
        policy_payload({"core": 70.0, "services": 60.0}),
    )

    assert report["status"] == "failed"
    assert report["regressions"] == ["core"]
    assert report["domains"]["core"]["regression"] is True


def test_improvement_passes_and_reports_target_state() -> None:
    report = evaluate(
        coverage_payload(82, 76),
        policy_payload({"core": 70.0, "services": 60.0}),
    )

    assert report["status"] == "passed"
    assert report["domains"]["core"]["target_met"] is True
    assert report["domains"]["services"]["target_met"] is True
