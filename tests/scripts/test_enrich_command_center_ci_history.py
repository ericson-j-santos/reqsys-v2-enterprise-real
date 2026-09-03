import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.enrich_command_center_ci_history import summarize_history  # noqa: E402


def record(idx: int, signal: str, success: float = 90.0, failure: float = 4.0, p95: float = 30.0, cv: float = 50.0):
    return {
        "generated_at": f"2026-09-03T0{idx}:00:00Z",
        "run_id": str(idx),
        "status": "warning",
        "current": {"success_rate_percent": success, "failure_rate_percent": failure, "p95_seconds": p95, "cv_percent": cv},
        "baseline_comparison": {"overall_signal": signal},
    }


class CommandCenterHistoryTests(unittest.TestCase):
    def test_insufficient_data_before_three_observations(self):
        summary = summarize_history([record(1, "improved"), record(2, "improved")])
        self.assertEqual(summary["sustainability"], "insufficient_data")

    def test_sustained_improvement_requires_majority_without_regression(self):
        summary = summarize_history([record(1, "improved"), record(2, "stable"), record(3, "improved"), record(4, "improved")])
        self.assertEqual(summary["sustainability"], "sustained_improvement")
        self.assertFalse(summary["creates_gate"])

    def test_regression_watch_when_regressions_are_recurrent(self):
        summary = summarize_history([record(1, "regressed"), record(2, "stable"), record(3, "regressed"), record(4, "improved")])
        self.assertEqual(summary["sustainability"], "regression_watch")

    def test_recent_averages_use_lookback(self):
        summary = summarize_history([record(1, "stable", success=80), record(2, "improved", success=90), record(3, "improved", success=100)], lookback=2)
        self.assertEqual(summary["recent_averages"]["success_rate_percent"], 95.0)


if __name__ == "__main__":
    unittest.main()
