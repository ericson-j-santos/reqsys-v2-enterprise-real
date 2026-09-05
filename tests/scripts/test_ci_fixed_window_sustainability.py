#!/usr/bin/env python3
import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from ci_fixed_window_sustainability import summarize_history, transition  # noqa: E402
from enrich_command_center_ci_fixed_history import enrich  # noqa: E402


def record(idx: int, *, success=90.0, failure=4.0, p95=30.0, cv=50.0, eligible=True, policy="p1", window=None):
    start = window or f"2026-09-05T{idx:02d}:40:00+00:00"
    return {
        "generated_at": f"2026-09-05T{idx:02d}:45:00+00:00",
        "run_id": str(idx),
        "current": {
            "success_rate_percent": success,
            "failure_rate_percent": failure,
            "p95_seconds": p95,
            "cv_percent": cv,
        },
        "baseline_comparison": {"overall_signal": "mixed"},
        "collection_window": {
            "mode": "fixed_time",
            "policy_id": policy,
            "window_id": f"{policy}:{start}",
            "start_at": start,
            "end_at": start,
            "sample_eligible": eligible,
            "collection_complete": True,
            "completion_coverage_percent": 100,
            "eligibility_reason_codes": [] if eligible else ["completed_runs_below_minimum"],
        },
    }


class FixedWindowSustainabilityTests(unittest.TestCase):
    def test_transition_detects_improvement(self):
        before = record(1, success=80, failure=10, p95=50, cv=70)
        after = record(2, success=90, failure=5, p95=30, cv=50)
        self.assertEqual(transition(before, after)["overall_signal"], "improved")

    def test_requires_three_eligible_windows(self):
        summary = summarize_history([record(1), record(2)])
        self.assertEqual(summary["sustainability"], "insufficient_data")

    def test_sustained_improvement_uses_hour_to_hour_transitions(self):
        rows = [
            record(1, success=80, failure=10, p95=60, cv=80),
            record(2, success=85, failure=8, p95=50, cv=70),
            record(3, success=90, failure=5, p95=40, cv=60),
        ]
        summary = summarize_history(rows)
        self.assertEqual(summary["sustainability"], "sustained_improvement")
        self.assertEqual(summary["sustainability_basis"], "homogeneous_fixed_time_windows")
        self.assertFalse(summary["creates_gate"])

    def test_ineligible_window_is_context_only(self):
        summary = summarize_history([record(1), record(2, eligible=False), record(3)])
        self.assertEqual(summary["eligible_records"], 2)
        self.assertEqual(summary["sustainability"], "insufficient_data")
        self.assertEqual(len(summary["recent_context"]), 3)

    def test_does_not_mix_policy_versions(self):
        summary = summarize_history([record(1, policy="old"), record(2), record(3), record(4)])
        self.assertEqual(summary["active_policy_id"], "p1")
        self.assertEqual(summary["eligible_records"], 3)

    def test_enrich_writes_command_center_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "out"
            output.mkdir()
            (output / "workflow-command-center.json").write_text("{}", encoding="utf-8")
            (output / "workflow-command-center.html").write_text("<html><body></body></html>", encoding="utf-8")
            history = root / "history.jsonl"
            rows = [record(1), record(2), record(3)]
            history.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            summary = enrich(output, history)
            self.assertEqual(summary["sustainability_basis"], "homogeneous_fixed_time_windows")
            self.assertTrue((output / "ci-process-improvement-history.json").exists())
            self.assertIn("janelas horárias", (output / "workflow-command-center.html").read_text(encoding="utf-8"))

    def test_duplicate_window_counts_once(self):
        first = record(1, window="2026-09-05T10:40:00+00:00")
        replacement = record(2, window="2026-09-05T10:40:00+00:00")
        replacement["collection_window"]["window_id"] = first["collection_window"]["window_id"]
        summary = summarize_history([first, replacement])
        self.assertEqual(summary["records"], 1)


if __name__ == "__main__":
    unittest.main()
