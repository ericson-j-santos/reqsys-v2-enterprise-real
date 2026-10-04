#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_ci_process_improvement_analytics import build_summary, percentile, render_markdown  # noqa: E402


def make_run(
    run_id,
    name,
    created,
    started,
    updated,
    conclusion="success",
    run_attempt=1,
):
    return {
        "id": run_id,
        "name": name,
        "event": "pull_request",
        "status": "completed",
        "conclusion": conclusion,
        "head_branch": "feature/test",
        "head_sha": f"sha-{run_id}",
        "html_url": f"https://example.test/runs/{run_id}",
        "created_at": created,
        "run_started_at": started,
        "updated_at": updated,
        "run_attempt": run_attempt,
    }


class ProcessImprovementAnalyticsTests(unittest.TestCase):
    def test_percentile_linear_interpolation(self):
        self.assertEqual(percentile([10, 20, 30, 40], 0.50), 25.0)
        self.assertEqual(percentile([10, 20, 30, 40], 0.95), 38.5)

    def test_summary_calculates_process_improvement_metrics(self):
        runs = [
            make_run(1, "CI", "2026-09-02T10:00:00Z", "2026-09-02T10:00:10Z", "2026-09-02T10:02:10Z"),
            make_run(2, "CI", "2026-09-02T09:00:00Z", "2026-09-02T09:00:20Z", "2026-09-02T09:03:20Z", "failure"),
            make_run(3, "Security", "2026-09-02T08:00:00Z", "2026-09-02T08:00:30Z", "2026-09-02T08:04:30Z", run_attempt=2),
            make_run(4, "CI", "2026-09-02T07:00:00Z", "2026-09-02T07:00:40Z", "2026-09-02T07:05:40Z"),
            make_run(5, "Security", "2026-09-02T06:00:00Z", "2026-09-02T06:00:50Z", "2026-09-02T06:06:50Z", "failure"),
            make_run(6, "CI", "2026-09-02T05:00:00Z", "2026-09-02T05:01:00Z", "2026-09-02T05:07:00Z"),
        ]
        summary = build_summary(
            runs,
            repository="owner/repo",
            window_runs=100,
            generated_at="2026-09-02T12:00:00+00:00",
        )

        self.assertEqual(summary["completed_runs"], 6)
        self.assertEqual(summary["failure_count"], 2)
        self.assertEqual(summary["rerun_count"], 1)
        self.assertEqual(summary["first_pass_success_count"], 3)
        self.assertEqual(summary["first_pass_success_rate_percent"], 50.0)
        self.assertEqual(summary["rerun_rate_percent"], 16.67)
        self.assertEqual(summary["p95_queue_seconds"], 57.5)
        self.assertGreater(summary["stddev_seconds"], 0)
        self.assertGreater(summary["cv_percent"], 0)
        self.assertTrue(summary["trend_comparison"]["available"])
        self.assertEqual(summary["failure_pareto"][0]["failures"], 1)
        self.assertEqual(summary["failure_pareto"][-1]["cumulative_share_percent"], 100.0)
        self.assertGreater(summary["throughput"]["runs_per_hour"], 0)

    def test_pareto_prioritizes_workflow_with_most_failures(self):
        runs = [
            make_run(1, "CI", "2026-09-02T10:00:00Z", "2026-09-02T10:00:00Z", "2026-09-02T10:01:00Z", "failure"),
            make_run(2, "CI", "2026-09-02T09:00:00Z", "2026-09-02T09:00:00Z", "2026-09-02T09:01:00Z", "failure"),
            make_run(3, "Security", "2026-09-02T08:00:00Z", "2026-09-02T08:00:00Z", "2026-09-02T08:01:00Z", "failure"),
            make_run(4, "Deploy", "2026-09-02T07:00:00Z", "2026-09-02T07:00:00Z", "2026-09-02T07:01:00Z"),
        ]
        summary = build_summary(runs, repository="owner/repo", window_runs=100)
        self.assertEqual(summary["failure_pareto"][0]["name"], "CI")
        self.assertEqual(summary["failure_pareto"][0]["share_percent"], 66.67)
        self.assertEqual(summary["failure_pareto"][-1]["cumulative_share_percent"], 100.0)

    def test_markdown_exposes_new_metrics(self):
        runs = [
            make_run(1, "CI", "2026-09-02T10:00:00Z", "2026-09-02T10:00:10Z", "2026-09-02T10:01:10Z"),
            make_run(2, "CI", "2026-09-02T09:00:00Z", "2026-09-02T09:00:10Z", "2026-09-02T09:01:10Z"),
            make_run(3, "CI", "2026-09-02T08:00:00Z", "2026-09-02T08:00:10Z", "2026-09-02T08:01:10Z"),
            make_run(4, "CI", "2026-09-02T07:00:00Z", "2026-09-02T07:00:10Z", "2026-09-02T07:01:10Z"),
        ]
        markdown = render_markdown(build_summary(runs, repository="owner/repo", window_runs=100))
        self.assertIn("First-pass success", markdown)
        self.assertIn("Coefficient of variation", markdown)
        self.assertIn("Failure Pareto", markdown)
        self.assertIn("Trend comparison", markdown)


if __name__ == "__main__":
    unittest.main()
