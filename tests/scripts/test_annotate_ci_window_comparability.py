import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.annotate_ci_window_comparability import (  # noqa: E402
    apply_window_comparability,
    build_window_comparability,
)


def analytics(completed=62, span=0.58, window_runs=100):
    return {
        "schema_version": "1.0.3",
        "window_runs": window_runs,
        "completed_runs": completed,
        "success_count": 48,
        "failure_count": 4,
        "cancelled_count": 4,
        "skipped_count": 6,
        "throughput": {"window_span_hours": span},
    }


def baseline(completed=62, span=0.58, window_runs=100):
    return {
        "sample": {"window_runs": window_runs, "completed_runs": completed, "window_span_hours": span},
        "quality": {"success_count": 48, "failure_count": 4, "cancelled_count": 4, "skipped_count": 6},
    }


class WindowComparabilityTests(unittest.TestCase):
    def test_comparable_when_sample_size_and_span_are_similar(self):
        result = build_window_comparability(analytics(completed=65, span=0.62), baseline())
        self.assertTrue(result["available"])
        self.assertTrue(result["comparable_to_baseline"])
        self.assertEqual(result["reason_codes"], [])
        self.assertFalse(result["creates_gate"])

    def test_rejects_effective_sample_size_outside_range(self):
        result = build_window_comparability(analytics(completed=95, span=0.60), baseline())
        self.assertFalse(result["comparable_to_baseline"])
        self.assertIn("completed_runs_ratio_out_of_range", result["reason_codes"])

    def test_rejects_window_span_outside_range(self):
        result = build_window_comparability(analytics(completed=62, span=1.53), baseline())
        self.assertFalse(result["comparable_to_baseline"])
        self.assertIn("window_span_ratio_out_of_range", result["reason_codes"])

    def test_missing_baseline_metadata_is_explicitly_unavailable(self):
        result = build_window_comparability(analytics(), {"sample": {"window_runs": 100}})
        self.assertFalse(result["available"])
        self.assertFalse(result["comparable_to_baseline"])
        self.assertEqual(result["mode"], "descriptive-only")
        self.assertFalse(result["creates_gate"])

    def test_apply_is_idempotent_and_preserves_schema_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analytics_path = root / "analytics.json"
            markdown_path = root / "analytics.md"
            baseline_path = root / "baseline.json"
            analytics_path.write_text(json.dumps(analytics()), encoding="utf-8")
            markdown_path.write_text("# CI Lead Time Analytics\n", encoding="utf-8")
            baseline_path.write_text(json.dumps(baseline()), encoding="utf-8")

            first = apply_window_comparability(analytics_path, markdown_path, baseline_path)
            second = apply_window_comparability(analytics_path, markdown_path, baseline_path)
            self.assertEqual(first["schema_version"], "1.0.3")
            self.assertEqual(second["schema_version"], "1.0.3")
            self.assertEqual(markdown_path.read_text(encoding="utf-8").count("## Statistical window comparability"), 1)


if __name__ == "__main__":
    unittest.main()
