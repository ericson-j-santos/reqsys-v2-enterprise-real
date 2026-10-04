import unittest

from scripts.smoke_executive_sync_stability_index_public_trend_sync_state_final import (
    CARD_ID,
    CARD_KEY,
    append_history,
    validate,
)


class FinalPublicTrendSyncSmokeTest(unittest.TestCase):
    def setUp(self):
        self.card = {
            "status": "eligible-for-human-review",
            "coverage_complete": True,
            "synchronized": True,
            "total_samples": 9,
            "weighted_pass_rate_percent": 100.0,
            "minimum_stable_sequence": 3,
            "eligible_for_human_review": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }
        self.html = f'<main><section id="{CARD_ID}"></section></main>'
        self.runtime = {"production_ready": True, "cards": {CARD_KEY: dict(self.card)}}
        self.brief = {"production_ready": True, CARD_KEY: dict(self.card)}

    def test_valid_sync_is_ok_and_non_blocking(self):
        sample = validate(self.html, self.runtime, self.brief, "prod")
        self.assertEqual("PUBLIC_FINAL_SYNC_OK", sample["status"])
        self.assertTrue(sample["synchronized"])
        self.assertFalse(sample["production_blocker"])
        self.assertTrue(sample["human_approval_required"])

    def test_drift_is_review_only(self):
        brief = dict(self.brief)
        brief[CARD_KEY] = dict(self.card, total_samples=8)
        sample = validate(self.html, self.runtime, brief, "stg")
        self.assertEqual("PUBLIC_FINAL_SYNC_REVIEW", sample["status"])
        self.assertIn("runtime/brief drift: total_samples", sample["errors"])
        self.assertFalse(sample["production_blocker"])

    def test_missing_card_is_review(self):
        sample = validate("<main></main>", self.runtime, self.brief, "dev")
        self.assertEqual("PUBLIC_FINAL_SYNC_REVIEW", sample["status"])
        self.assertIn("public card must be present exactly once", sample["errors"])

    def test_history_is_idempotent_and_environment_scoped(self):
        sample = validate(self.html, self.runtime, self.brief, "dev")
        first = append_history({}, sample)
        second = append_history(first, sample)
        self.assertEqual(1, second["summary"]["sample_count"])
        self.assertEqual(1, second["summary"]["stable_sequence"])
        self.assertEqual("dev", second["summary"]["environment"])


if __name__ == "__main__":
    unittest.main()
