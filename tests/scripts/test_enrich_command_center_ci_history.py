import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.enrich_command_center_ci_history import summarize_history  # noqa: E402


def record(
    idx: int,
    signal: str,
    success: float = 90.0,
    failure: float = 4.0,
    p95: float = 30.0,
    cv: float = 50.0,
    comparable: bool | None = True,
):
    item = {
        "generated_at": f"2026-09-03T{idx:02d}:00:00Z",
        "run_id": str(idx),
        "status": "warning",
        "current": {
            "success_rate_percent": success,
            "failure_rate_percent": failure,
            "p95_seconds": p95,
            "cv_percent": cv,
        },
        "baseline_comparison": {"overall_signal": signal},
    }
    if comparable is not None:
        item["window_comparability"] = {
            "comparable_to_baseline": comparable,
            "reason_codes": [] if comparable else ["window_span_ratio_out_of_range"],
        }
    return item


class CommandCenterHistoryTests(unittest.TestCase):
    def test_insufficient_data_before_three_comparable_observations(self):
        summary = summarize_history([record(1, "improved"), record(2, "improved")])
        self.assertEqual(summary["sustainability"], "insufficient_data")
        self.assertEqual(summary["comparable_records"], 2)

    def test_sustained_improvement_requires_majority_without_regression(self):
        summary = summarize_history(
            [record(1, "improved"), record(2, "stable"), record(3, "improved"), record(4, "improved")]
        )
        self.assertEqual(summary["sustainability"], "sustained_improvement")
        self.assertFalse(summary["creates_gate"])
        self.assertEqual(summary["sustainability_basis"], "comparable_to_baseline_only")

    def test_regression_watch_when_comparable_regressions_are_recurrent(self):
        summary = summarize_history(
            [record(1, "regressed"), record(2, "stable"), record(3, "regressed"), record(4, "improved")]
        )
        self.assertEqual(summary["sustainability"], "regression_watch")

    def test_non_comparable_records_do_not_change_sustainability(self):
        summary = summarize_history(
            [
                record(1, "improved", comparable=True),
                record(2, "improved", comparable=True),
                record(3, "improved", comparable=True),
                record(4, "regressed", comparable=False),
                record(5, "regressed", comparable=False),
            ]
        )
        self.assertEqual(summary["sustainability"], "sustained_improvement")
        self.assertEqual(summary["signals"]["regressed"], 0)
        self.assertEqual(summary["excluded_non_comparable_records"], 2)
        self.assertEqual(len(summary["series"]), 3)
        self.assertEqual(len(summary["recent_context"]), 5)

    def test_missing_comparability_is_excluded_conservatively(self):
        summary = summarize_history(
            [
                record(1, "improved", comparable=None),
                record(2, "improved", comparable=True),
                record(3, "improved", comparable=True),
            ]
        )
        self.assertEqual(summary["sustainability"], "insufficient_data")
        self.assertEqual(summary["comparable_records"], 2)
        self.assertEqual(summary["excluded_non_comparable_records"], 1)

    def test_recent_averages_use_only_comparable_lookback(self):
        summary = summarize_history(
            [
                record(1, "stable", success=10, comparable=False),
                record(2, "improved", success=90, comparable=True),
                record(3, "improved", success=100, comparable=True),
            ],
            lookback=2,
        )
        self.assertEqual(summary["recent_averages"]["success_rate_percent"], 95.0)
        self.assertEqual(summary["lookback"], 2)

    def test_recent_context_exposes_comparability_reason(self):
        summary = summarize_history([record(1, "mixed", comparable=False)])
        self.assertFalse(summary["recent_context"][0]["comparable_to_baseline"])
        self.assertIn("window_span_ratio_out_of_range", summary["recent_context"][0]["comparability_reason_codes"])


if __name__ == "__main__":
    unittest.main()
