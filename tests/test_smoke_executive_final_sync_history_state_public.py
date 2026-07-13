import unittest

from scripts.smoke_executive_final_sync_history_state_public import (
    STATUS_OK,
    STATUS_REVIEW,
    append_history,
    evaluate,
)


class ExecutiveFinalSyncHistoryStatePublicSmokeTest(unittest.TestCase):
    def setUp(self):
        self.card = {
            "status": "eligible-for-human-review",
            "coverage_complete": True,
            "synchronized": True,
            "total_samples": 9,
            "weighted_pass_rate_percent": 100.0,
            "minimum_stable_sequence": 3,
            "common_fingerprint": "abc123",
            "eligible_for_human_review": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }
        self.runtime = {"cards": {"executive_final_sync_history_state": dict(self.card)}}
        self.brief = {"executive_final_sync_history_state": dict(self.card)}
        self.html = '<main><section id="executive-final-sync-history-state"></section></main>'

    def test_valid_public_contract_passes(self):
        evidence = evaluate(self.html, self.runtime, self.brief)
        self.assertEqual(STATUS_OK, evidence["status"])
        self.assertTrue(evidence["available"])
        self.assertTrue(evidence["synchronized"])

    def test_contract_drift_requires_review(self):
        brief = {"executive_final_sync_history_state": dict(self.card, total_samples=8)}
        evidence = evaluate(self.html, self.runtime, brief)
        self.assertEqual(STATUS_REVIEW, evidence["status"])
        self.assertIn("runtime and executive brief contracts diverge", evidence["errors"])

    def test_missing_card_requires_review(self):
        evidence = evaluate("<main></main>", self.runtime, self.brief)
        self.assertEqual(STATUS_REVIEW, evidence["status"])
        self.assertFalse(evidence["available"])

    def test_history_is_idempotent_and_environment_scoped(self):
        evidence = evaluate(self.html, self.runtime, self.brief)
        first = append_history({}, "dev", evidence)
        second = append_history(first, "dev", evidence)
        self.assertEqual(1, second["summary"]["sample_count"])
        self.assertEqual(1, second["summary"]["stable_sequence"])
        self.assertEqual("dev", second["samples"][0]["environment"])

    def test_unsafe_guardrails_require_review(self):
        runtime = {"cards": {"executive_final_sync_history_state": dict(self.card, mode="blocking")}}
        evidence = evaluate(self.html, runtime, self.brief)
        self.assertEqual(STATUS_REVIEW, evidence["status"])
        self.assertIn("mode must be report-only", evidence["errors"])


if __name__ == "__main__":
    unittest.main()
