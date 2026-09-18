import unittest

from scripts.enrich_executive_final_trend_sync_history_state import consolidate, enrich


def history(status="PUBLIC_FINAL_TREND_SYNC_OK", fingerprint="fp", samples=3, streak=3):
    return {
        "samples": [{"status": status, "id": index} for index in range(samples)],
        "stable_streak": streak,
        "fingerprint": fingerprint,
    }


class ExecutiveFinalTrendSyncHistoryStateTest(unittest.TestCase):
    def test_eligible_with_complete_stable_evidence(self):
        result = consolidate({env: history() for env in ("DEV", "STG", "PROD")})
        self.assertEqual("eligible-for-human-review", result["status"])
        self.assertTrue(result["eligible_for_human_review"])
        self.assertFalse(result["production_blocker"])

    def test_detects_missing_environment(self):
        result = consolidate({"DEV": history(), "STG": history(), "PROD": {}})
        self.assertEqual("insufficient-environment-coverage", result["status"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_detects_drift(self):
        result = consolidate({"DEV": history(fingerprint="a"), "STG": history(fingerprint="a"), "PROD": history(fingerprint="b")})
        self.assertEqual("drift-detected", result["status"])

    def test_collects_until_minimum_evidence(self):
        result = consolidate({env: history(samples=2, streak=2) for env in ("DEV", "STG", "PROD")})
        self.assertEqual("collecting-evidence", result["status"])

    def test_enrichment_is_idempotent_and_preserves_production_state(self):
        state = {"production_ready": False, "cards": {}}
        brief = {"indicators": {}}
        result = consolidate({env: history() for env in ("DEV", "STG", "PROD")})
        first_state, first_brief = enrich(state, brief, result)
        second_state, second_brief = enrich(first_state, first_brief, result)
        self.assertEqual(first_state, second_state)
        self.assertEqual(first_brief, second_brief)
        self.assertFalse(second_state["production_ready"])


if __name__ == "__main__":
    unittest.main()
