from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scripts.performance_slo_artifact_eligibility import (
    EligibilityError,
    assess_eligibility,
)
from scripts.performance_slo_error_budget import (
    build_report,
    build_slos,
    detect_sustained_degradation,
)

NOW = datetime(2026, 8, 25, 17, 0, tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _snapshot(
    offset: int,
    *,
    p95: float = 100.0,
    p99: float = 120.0,
    throughput: float = 20.0,
    error_rate: float = 0.0,
    lcp: float = 2000.0,
) -> dict:
    return {
        "observed_at": _iso(NOW - timedelta(hours=offset)),
        "run_id": f"run-{offset}",
        "head_branch": "main",
        "mode": "scheduled-baseline",
        "api": {
            "/health": {
                "p95_ms": p95,
                "p99_ms": p99,
                "throughput_rps": throughput,
                "error_rate_percent": error_rate,
            }
        },
        "browser": {
            "event_loop_lag_p95_ms": 1.0,
            "event_loop_lag_max_ms": 2.0,
            "max_long_task_ms": 40.0,
            "lcp_ms": lcp,
            "heap_after_gc_mb": 9.0,
            "gc_roundtrip_ms": 20.0,
        },
    }


def _policy(minimum_samples: int = 5) -> dict:
    return {
        "policy_version": "test",
        "browser": {
            "max_event_loop_lag_p95_ms": 100,
            "max_event_loop_lag_max_ms": 250,
            "max_long_task_ms": 250,
            "max_lcp_ms": 4000,
            "max_heap_after_gc_mb": 128,
            "max_gc_roundtrip_ms": 750,
        },
        "history": {
            "regression": {
                "max_latency_increase_percent": 30,
                "max_throughput_drop_percent": 30,
                "max_error_rate_increase_pp": 1,
                "max_browser_metric_increase_percent": 30,
            }
        },
        "performance_slo": {
            "window_days": 7,
            "minimum_samples": minimum_samples,
            "error_budget_warning_remaining_percent": 25,
            "targets": {
                "api_latency_good_percent": 95,
                "api_reliability_good_percent": 99,
                "api_capacity_good_percent": 95,
                "browser_runtime_good_percent": 95,
            },
            "sustained_degradation": {
                "required_consecutive": 3,
                "reference_window_days": 7,
                "minimum_reference_samples": 5,
            },
        },
        "endpoints": [
            {
                "path": "/health",
                "budget": {
                    "max_p95_ms": 1500,
                    "max_p99_ms": 2500,
                    "max_error_rate_percent": 0,
                    "min_throughput_rps": 2,
                },
            }
        ],
    }


def _history(snapshots: list[dict], regressions: list[dict] | None = None) -> dict:
    ordered = sorted(snapshots, key=lambda item: item["observed_at"])
    return {
        "current": ordered[-1],
        "snapshots": ordered,
        "regressions": regressions or [],
    }


class PerformanceSloTests(unittest.TestCase):
    def test_insufficient(self) -> None:
        slos = build_slos(_history([_snapshot(1), _snapshot(0)]), _policy(), environment="prod")
        self.assertTrue(all(item["status"] == "no_data" for item in slos))

    def test_error_budget_boundary_warns(self) -> None:
        snapshots = [_snapshot(index) for index in range(20)]
        snapshots[19] = _snapshot(19, p95=2000, p99=2600)
        latency = next(
            item
            for item in build_slos(_history(snapshots), _policy(), environment="prod")
            if item["slo_id"] == "performance_api_latency"
        )
        self.assertEqual(latency["actual_percent"], 95.0)
        self.assertEqual(latency["error_budget_remaining_percent"], 0.0)
        self.assertFalse(latency["breach"])
        self.assertTrue(latency["warning"])

    def test_breach_blocks(self) -> None:
        snapshots = [_snapshot(index) for index in range(10)]
        snapshots[9] = _snapshot(9, error_rate=5)
        report = build_report(history_report=_history(snapshots), policy=_policy())
        self.assertEqual(report["status"], "blocked")

    def test_three_consecutive(self) -> None:
        reference = [_snapshot(index + 3, p95=100) for index in range(5)]
        tail = [_snapshot(2, p95=150), _snapshot(1, p95=150), _snapshot(0, p95=150)]
        report = detect_sustained_degradation(_history(reference + tail), _policy())
        self.assertTrue(any(item["metric"] == "p95_ms" for item in report["findings"]))

        non_consecutive = [_snapshot(2, p95=150), _snapshot(1, p95=100), _snapshot(0, p95=150)]
        self.assertEqual(
            detect_sustained_degradation(_history(reference + non_consecutive), _policy())["findings"],
            [],
        )

    def test_single_regression_watch(self) -> None:
        snapshots = [_snapshot(index) for index in range(8)]
        report = build_report(
            history_report=_history(snapshots, [{"metric": "p95_ms"}]),
            policy=_policy(),
        )
        self.assertEqual(report["status"], "watch")

    def test_sustained_blocks(self) -> None:
        reference = [_snapshot(index + 3, p95=100) for index in range(5)]
        tail = [_snapshot(2, p95=150), _snapshot(1, p95=150), _snapshot(0, p95=150)]
        report = build_report(history_report=_history(reference + tail), policy=_policy())
        self.assertEqual(report["status"], "blocked")
        self.assertGreater(report["summary"]["sustained_degradations_total"], 0)


class PerformanceSloArtifactEligibilityTests(unittest.TestCase):
    def test_skipped_runtime_is_safe_ineligible(self) -> None:
        result = assess_eligibility(
            {"jobs": [{"name": "Measure live runtime performance", "conclusion": "skipped"}]},
            {"artifacts": []},
        )
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "runtime_measurement_skipped")

    def test_success_runtime_requires_main_artifact(self) -> None:
        result = assess_eligibility(
            {"jobs": [{"name": "Measure live runtime performance", "conclusion": "success"}]},
            {
                "artifacts": [
                    {
                        "id": 123,
                        "name": "dynamic-performance-evidence-main",
                        "expired": False,
                    }
                ]
            },
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["artifact_id"], 123)

    def test_success_runtime_without_artifact_fails_closed(self) -> None:
        with self.assertRaises(EligibilityError):
            assess_eligibility(
                {"jobs": [{"name": "Measure live runtime performance", "conclusion": "success"}]},
                {"artifacts": []},
            )

    def test_missing_runtime_job_fails_closed(self) -> None:
        with self.assertRaises(EligibilityError):
            assess_eligibility({"jobs": []}, {"artifacts": []})


if __name__ == "__main__":
    unittest.main()
