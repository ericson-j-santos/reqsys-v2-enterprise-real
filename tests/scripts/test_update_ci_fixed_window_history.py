#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from update_ci_fixed_window_history import history_record, merge_history  # noqa: E402


def analytics(run_id="1", window_id="p:10:40", eligible=True):
    return {
        "generated_at": "2026-09-05T11:45:00+00:00",
        "run_id": run_id,
        "status": "warning",
        "baseline_comparison": {"available": True, "mode": "report-only", "creates_gate": False},
        "collection_window": {
            "policy_id": "p",
            "window_id": window_id,
            "mode": "fixed_time",
            "duration_minutes": 60,
            "settle_minutes": 5,
            "anchor_minute": 40,
            "start_at": "2026-09-05T09:40:00+00:00",
            "end_at": "2026-09-05T10:40:00+00:00",
            "runs_in_window": 40,
            "completed_runs": 40,
            "completion_coverage_percent": 100,
            "collection_complete": True,
            "sample_eligible": eligible,
            "eligibility_reason_codes": [],
        },
    }


class FixedWindowHistoryTests(unittest.TestCase):
    def test_persists_collection_policy(self):
        record = history_record(analytics())
        self.assertEqual(record["schema_version"], "1.0.2")
        self.assertEqual(record["collection_window"]["duration_minutes"], 60)
        self.assertTrue(record["collection_window"]["sample_eligible"])
        self.assertFalse(record["collection_window"]["creates_gate"])

    def test_same_window_replaces_previous_run(self):
        first = history_record(analytics("1"))
        second_payload = analytics("2")
        second_payload["generated_at"] = "2026-09-05T11:50:00+00:00"
        second = history_record(second_payload)
        merged = merge_history([first], second)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["run_id"], "2")

    def test_different_windows_are_preserved(self):
        first = history_record(analytics("1", "p:10:40"))
        second = history_record(analytics("2", "p:11:40"))
        self.assertEqual(len(merge_history([first], second)), 2)

    def test_legacy_record_keeps_run_id_key(self):
        legacy = {"generated_at": "2026-09-05T10:00:00Z", "run_id": "old"}
        fixed = history_record(analytics())
        self.assertEqual(len(merge_history([legacy], fixed)), 2)


if __name__ == "__main__":
    unittest.main()
