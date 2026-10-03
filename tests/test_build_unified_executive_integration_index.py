import unittest

from scripts.build_unified_executive_integration_index import build


class UnifiedExecutiveIntegrationIndexTests(unittest.TestCase):
    def test_green_when_all_sources_are_stable(self):
        parallelism = {
            "status": "STABLE",
            "parallelism_decision": "INCREASE_SAFE",
            "window": {"merged_pull_requests": 8},
            "metrics": {
                "average_lead_time_minutes": 42,
                "rerun_rate_percent": 4,
                "merge_queue_success_rate_percent": 100,
            },
        }
        result = build(parallelism, {"status": "healthy"}, {"status": "passed"})
        self.assertEqual(result["status"], "EXECUTIVE_GREEN")
        self.assertEqual(result["risk"], "low")
        self.assertFalse(result["production"]["promotion_allowed"])
        self.assertTrue(result["production"]["human_approval_required"])

    def test_missing_evidence_blocks_green(self):
        result = build({}, {"status": "healthy"}, {"status": "passed"})
        self.assertEqual(result["status"], "EVIDENCE_INCOMPLETE")
        self.assertFalse(result["evidence"]["complete"])

    def test_unstable_ci_requires_attention(self):
        result = build({"status": "OBSERVATION_REQUIRED", "metrics": {}}, {"status": "healthy"}, {"status": "passed"})
        self.assertEqual(result["status"], "EXECUTIVE_ATTENTION")
        self.assertEqual(result["next_safe_action"], "KEEP_LIMITS_AND_REVIEW")


if __name__ == "__main__":
    unittest.main()
