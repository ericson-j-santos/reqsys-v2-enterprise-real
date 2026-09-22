import unittest

from scripts.enrich_executive_sync_stability_index_public_trend_sync_state import (
    CARD_KEY,
    build_state,
    enrich,
)


def history(environment: str, count: int = 3, synchronized: bool = True, passed: bool = True) -> dict:
    status = "PUBLIC_TREND_SYNC_OK" if passed else "PUBLIC_TREND_SYNC_REVIEW"
    return {
        "samples": [
            {"environment": environment, "status": status, "synchronized": synchronized}
            for _ in range(count)
        ],
        "summary": {
            "environment": environment,
            "sample_count": count,
            "pass_rate": 100.0 if passed else 0.0,
            "stable_sequence": count if passed else 0,
        },
    }


class ExecutiveSyncTrendSyncStateTest(unittest.TestCase):
    def test_sufficient_evidence_is_only_human_review_eligible(self):
        state = build_state({name: history(name) for name in ("dev", "stg", "prod")})
        self.assertEqual("eligible-for-human-review", state["status"])
        self.assertTrue(state["eligible_for_human_review"])
        self.assertFalse(state["production_blocker"])
        self.assertEqual("report-only", state["mode"])

    def test_missing_environment_remains_collecting(self):
        state = build_state({"dev": history("dev"), "stg": history("stg")})
        self.assertEqual("insufficient-environment-coverage", state["status"])
        self.assertEqual(["prod"], state["missing_environments"])
        self.assertFalse(state["eligible_for_human_review"])

    def test_drift_is_detected_without_blocking_production(self):
        histories = {name: history(name) for name in ("dev", "stg", "prod")}
        histories["prod"] = history("prod", synchronized=False)
        state = build_state(histories)
        self.assertEqual("drift-detected", state["status"])
        self.assertFalse(state["production_blocker"])

    def test_insufficient_samples_keep_collecting(self):
        state = build_state({name: history(name, count=2) for name in ("dev", "stg", "prod")})
        self.assertEqual("collecting-evidence", state["status"])
        self.assertFalse(state["eligible_for_human_review"])

    def test_enrich_is_idempotent_and_preserves_production_state(self):
        runtime = {"production_ready": True, "cards": {"existing": {"status": "ok"}}}
        brief = {"production_ready": True}
        histories = {name: history(name) for name in ("dev", "stg", "prod")}
        first_runtime, first_brief = enrich(runtime, brief, histories)
        second_runtime, second_brief = enrich(first_runtime, first_brief, histories)
        self.assertEqual(first_runtime, second_runtime)
        self.assertEqual(first_brief, second_brief)
        self.assertTrue(second_runtime["production_ready"])
        self.assertTrue(second_brief["production_ready"])
        self.assertIn(CARD_KEY, second_runtime["cards"])


if __name__ == "__main__":
    unittest.main()
