import unittest

from scripts.build_parallelism_effect_index import build


class ParallelismEffectIndexTests(unittest.TestCase):
    def test_stable_window_allows_safe_increase(self):
        prs = [
            {
                "created_at": f"2026-07-{day:02d}T10:00:00Z",
                "merged_at": f"2026-07-{day:02d}T11:00:00Z",
                "mergeable": True,
            }
            for day in range(1, 6)
        ]
        runs = [
            {"status": "completed", "run_attempt": 1, "event": "merge_group", "name": "Governed Merge Queue", "conclusion": "success"}
            for _ in range(3)
        ]
        result = build(prs, runs)
        self.assertEqual(result["status"], "STABLE")
        self.assertEqual(result["parallelism_decision"], "INCREASE_SAFE")
        self.assertFalse(result["promotion_allowed"])

    def test_insufficient_or_unstable_window_keeps_limits(self):
        prs = [{"created_at": "2026-07-01T10:00:00Z", "merged_at": None, "mergeable": False}]
        runs = [
            {"status": "completed", "run_attempt": 2, "event": "merge_group", "name": "Governed Merge Queue", "conclusion": "failure"}
        ]
        result = build(prs, runs)
        self.assertEqual(result["status"], "OBSERVATION_REQUIRED")
        self.assertEqual(result["parallelism_decision"], "KEEP_LIMITS")
        self.assertTrue(result["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
