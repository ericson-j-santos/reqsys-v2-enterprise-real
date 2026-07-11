from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_domain_coverage import evaluate


def coverage_payload(core_percent: float, service_percent: float, backend_prefix: bool = True) -> dict:
    prefix = "backend/" if backend_prefix else ""
    return {
        "files": {
            f"{prefix}app/core/a.py": {
                "summary": {"covered_lines": int(core_percent), "num_statements": 100}
            },
            f"{prefix}app/services/b.py": {
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


def test_accepts_coverage_paths_relative_to_backend_working_directory() -> None:
    report = evaluate(coverage_payload(70, 60, backend_prefix=False), policy_payload())

    assert report["status"] == "baseline_required"
    assert report["invalid_domains"] == []
    assert report["domains"]["services"]["matched_files"] == ["app/services/b.py"]


def test_invalid_measurement_blocks_when_domain_has_no_matching_files() -> None:
    coverage = {"files": {"app/other/a.py": {"summary": {"covered_lines": 1, "num_statements": 1}}}}

    report = evaluate(coverage, policy_payload())

    assert report["status"] == "invalid_measurement"
    assert report["invalid_domains"] == ["core", "services"]


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


def test_versioned_policy_runtime_domain_matches_runtime_files() -> None:
    policy = json.loads(
        Path("config/domain-coverage-policy.json").read_text(encoding="utf-8")
    )
    coverage = {
        "files": {
            "app/core/runtime_boot.py": {
                "summary": {"covered_lines": 8, "num_statements": 10}
            },
            "app/services/requisitos_runtime_events.py": {
                "summary": {"covered_lines": 9, "num_statements": 10}
            },
            "app/api/runtime_analytics.py": {
                "summary": {"covered_lines": 7, "num_statements": 10}
            },
        }
    }

    report = evaluate(coverage, policy)

    assert "runtime" not in report["invalid_domains"]
    assert report["domains"]["runtime"]["matched_files"] == [
        "app/api/runtime_analytics.py",
        "app/core/runtime_boot.py",
        "app/services/requisitos_runtime_events.py",
    ]
