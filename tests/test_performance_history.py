from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scripts.performance_history import (
    build_baselines,
    build_report,
    detect_regressions,
    merge_and_prune,
)


NOW = datetime(2026, 8, 21, 19, 40, tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _snapshot(
    day_offset: int,
    *,
    run_id: str | None = None,
    p95: float = 100.0,
    p99: float = 120.0,
    throughput: float = 20.0,
    error_rate: float = 0.0,
    lcp: float = 2000.0,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "observed_at": _iso(NOW - timedelta(days=day_offset)),
        "run_id": run_id or f"run-{day_offset}",
        "event_name": "schedule",
        "head_sha": f"sha-{day_offset}",
        "head_branch": "main",
        "mode": "scheduled-baseline",
        "api": {
            "/health": {
                "p50_ms": 80.0,
                "p95_ms": p95,
                "p99_ms": p99,
                "avg_ms": 90.0,
                "max_ms": 140.0,
                "throughput_rps": throughput,
                "error_rate_percent": error_rate,
            }
        },
        "browser": {
            "event_loop_lag_p95_ms": 1.0,
            "event_loop_lag_max_ms": 2.0,
            "long_task_count": 1.0,
            "max_long_task_ms": 40.0,
            "lcp_ms": lcp,
            "heap_before_gc_mb": 10.0,
            "heap_after_gc_mb": 9.0,
            "heap_reclaimed_mb": 1.0,
            "gc_roundtrip_ms": 20.0,
        },
    }


def _policy(minimum_samples: int = 5, block_single: bool = False) -> dict:
    return {
        "policy_version": "test",
        "history": {
            "retention_days": 45,
            "windows_days": [7, 30],
            "minimum_baseline_samples": minimum_samples,
            "block_on_single_regression": block_single,
            "regression": {
                "max_latency_increase_percent": 30,
                "max_throughput_drop_percent": 30,
                "max_error_rate_increase_pp": 1,
                "max_browser_metric_increase_percent": 30,
            },
        },
    }


class PerformanceHistoryTests(unittest.TestCase):
    def test_merge_and_prune_deduplicates_and_removes_old_samples(self) -> None:
        old = _snapshot(50)
        duplicate_old = _snapshot(1, run_id="same")
        duplicate_new = _snapshot(0, run_id="same")
        current = _snapshot(0, run_id="current")

        merged = merge_and_prune(
            [old, duplicate_old, duplicate_new],
            current,
            retention_days=45,
        )

        self.assertNotIn(old, merged)
        self.assertEqual(len(merged), 3)

    def test_baseline_uses_prior_samples_and_median(self) -> None:
        history = [
            _snapshot(1, p95=90),
            _snapshot(2, p95=100),
            _snapshot(3, p95=110),
        ]
        current = _snapshot(0, run_id="current", p95=999)

        baselines = build_baselines(
            [*history, current],
            current,
            windows_days=[7],
            minimum_samples=3,
        )

        self.assertTrue(baselines["7"]["mature"])
        self.assertEqual(baselines["7"]["sample_count"], 3)
        self.assertEqual(baselines["7"]["api"]["/health"]["p95_ms"], 100.0)

    def test_regression_detects_latency_throughput_and_browser(self) -> None:
        history = [_snapshot(index) for index in range(1, 6)]
        current = _snapshot(
            0,
            run_id="current",
            p95=150,
            p99=180,
            throughput=12,
            lcp=3000,
        )
        baselines = build_baselines(
            [*history, current],
            current,
            windows_days=[7],
            minimum_samples=5,
        )

        findings = detect_regressions(
            current,
            baselines,
            _policy()["history"]["regression"],
        )

        metrics = {item["metric"] for item in findings}
        self.assertIn("p95_ms", metrics)
        self.assertIn("p99_ms", metrics)
        self.assertIn("throughput_rps", metrics)
        self.assertIn("lcp_ms", metrics)

    def test_report_is_insufficient_until_baseline_is_mature(self) -> None:
        history = [_snapshot(1), _snapshot(2)]
        current = _snapshot(0, run_id="current")

        report = build_report(
            policy=_policy(minimum_samples=5),
            history=history,
            current=current,
        )

        self.assertEqual(report["summary"]["status"], "insufficient_history")
        self.assertEqual(report["summary"]["regressions_total"], 0)

    def test_report_marks_single_regression_as_watch(self) -> None:
        history = [_snapshot(index, p95=100) for index in range(1, 6)]
        current = _snapshot(0, run_id="current", p95=140)

        report = build_report(
            policy=_policy(minimum_samples=5, block_single=False),
            history=history,
            current=current,
        )

        self.assertEqual(report["summary"]["status"], "watch")
        self.assertFalse(report["summary"]["block_on_single_regression"])
        self.assertTrue(
            any(
                item["metric"] == "p95_ms" and item["delta_percent"] == 40.0
                for item in report["regressions"]
            )
        )

    def test_legacy_policy_can_still_block_single_regression(self) -> None:
        history = [_snapshot(index, p95=100) for index in range(1, 6)]
        current = _snapshot(0, run_id="current", p95=140)

        report = build_report(
            policy=_policy(minimum_samples=5, block_single=True),
            history=history,
            current=current,
        )

        self.assertEqual(report["summary"]["status"], "blocked")
        self.assertTrue(report["summary"]["block_on_single_regression"])


if __name__ == "__main__":
    unittest.main()
