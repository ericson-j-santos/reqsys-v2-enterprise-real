import copy
import unittest

from scripts.enrich_executive_sync_stability_index_public_smoke_trend import (
    CARD_KEY,
    build_trend,
    enrich,
)


def history(environment: str, fingerprints: list[str], passed: bool = True) -> dict:
    samples = [
        {
            "environment": environment,
            "fingerprint": fingerprint,
            "passed": passed,
            "status": "PUBLIC_INDEX_SMOKE_OK" if passed else "PUBLIC_INDEX_SMOKE_REVIEW",
        }
        for fingerprint in fingerprints
    ]
    return {
        "samples": samples,
        "summary": {
            "environment": environment,
            "sample_count": len(samples),
            "pass_rate": 100.0 if passed else 0.0,
            "stable_sequence": len(samples) if passed else 0,
        },
    }


class ExecutiveSyncStabilityIndexPublicSmokeTrendTest(unittest.TestCase):
    def test_complete_synchronized_history_is_eligible(self):
        histories = {
            name: history(name, ["same", "same-2", "canonical"])
            for name in ("dev", "stg", "prod")
        }
        trend = build_trend(histories)
        self.assertTrue(trend["coverage_complete"])
        self.assertTrue(trend["synchronized"])
        self.assertTrue(trend["eligible_for_human_review"])
        self.assertEqual("eligible-for-human-review", trend["trend"])
        self.assertFalse(trend["production_blocker"])

    def test_missing_environment_remains_non_blocking(self):
        trend = build_trend({
            "dev": history("dev", ["a"]),
            "stg": history("stg", ["a"]),
        })
        self.assertFalse(trend["coverage_complete"])
        self.assertEqual(["prod"], trend["missing_environments"])
        self.assertEqual("insufficient-environment-coverage", trend["trend"])
        self.assertFalse(trend["eligible_for_human_review"])

    def test_cross_environment_drift_is_detected(self):
        histories = {
            "dev": history("dev", ["a", "a", "dev"]),
            "stg": history("stg", ["a", "a", "stg"]),
            "prod": history("prod", ["a", "a", "prod"]),
        }
        trend = build_trend(histories)
        self.assertFalse(trend["synchronized"])
        self.assertEqual("drift-detected", trend["trend"])
        self.assertFalse(trend["production_blocker"])

    def test_enrich_preserves_production_state_and_is_idempotent(self):
        runtime = {"production_ready": True, "cards": {"existing": {"status": "ok"}}}
        brief = {"production_ready": True}
        histories = {
            name: history(name, ["a", "b", "canonical"])
            for name in ("dev", "stg", "prod")
        }
        enriched_runtime, enriched_brief = enrich(runtime, brief, histories)
        second_runtime, second_brief = enrich(enriched_runtime, enriched_brief, histories)
        self.assertEqual(enriched_runtime, second_runtime)
        self.assertEqual(enriched_brief, second_brief)
        self.assertTrue(second_runtime["production_ready"])
        self.assertTrue(second_brief["production_ready"])
        self.assertIn(CARD_KEY, second_runtime["cards"])
        self.assertEqual("report-only", second_runtime["cards"][CARD_KEY]["mode"])


if __name__ == "__main__":
    unittest.main()
