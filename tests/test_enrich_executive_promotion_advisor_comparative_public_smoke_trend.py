import copy
import unittest

from scripts.enrich_executive_promotion_advisor_comparative_public_smoke_trend import (
    CARD_KEY,
    build_trend,
    enrich,
)


def history(sample_count=10, pass_rate=99.0, consistency=99.0, streak=6, status="PUBLIC_COMPARATIVE_SMOKE_PASSED"):
    return {
        "environments": {
            env: {
                "summary": {
                    "sample_count": sample_count,
                    "pass_rate_percent": pass_rate,
                    "visual_consistency_percent": consistency,
                    "stable_streak": streak,
                    "latest_status": status,
                }
            }
            for env in ("dev", "stg", "prod")
        }
    }


class ComparativePublicSmokeTrendTests(unittest.TestCase):
    def test_full_stable_history_is_only_eligible_for_human_review(self):
        trend = build_trend(history())
        self.assertEqual("eligible-for-human-review", trend["trend"])
        self.assertTrue(trend["eligible_for_human_review"])
        self.assertFalse(trend["production_blocker"])
        self.assertEqual("report-only", trend["mode"])

    def test_incomplete_coverage_never_becomes_ready(self):
        value = history()
        value["environments"].pop("prod")
        trend = build_trend(value)
        self.assertEqual("insufficient-environment-coverage", trend["trend"])
        self.assertFalse(trend["coverage_complete"])
        self.assertFalse(trend["eligible_for_human_review"])

    def test_degraded_environment_results_in_attention(self):
        value = history()
        value["environments"]["stg"]["summary"].update(
            pass_rate_percent=88.0,
            visual_consistency_percent=89.0,
            latest_status="PUBLIC_COMPARATIVE_SMOKE_REVIEW",
        )
        trend = build_trend(value)
        self.assertEqual("attention", trend["trend"])
        self.assertFalse(trend["production_blocker"])

    def test_enrichment_preserves_production_state(self):
        runtime = {"production_ready": True, "readiness": {"decision": "READY"}, "cards": {}}
        brief = {"production_ready": True, "decision": "READY"}
        enriched_runtime, enriched_brief = enrich(runtime, brief, history())
        self.assertTrue(enriched_runtime["production_ready"])
        self.assertEqual("READY", enriched_runtime["readiness"]["decision"])
        self.assertTrue(enriched_brief["production_ready"])
        self.assertEqual("READY", enriched_brief["decision"])
        self.assertIn(CARD_KEY, enriched_runtime["cards"])

    def test_enrichment_is_idempotent(self):
        runtime = {"cards": {}}
        brief = {}
        first_runtime, first_brief = enrich(runtime, brief, history())
        second_runtime, second_brief = enrich(copy.deepcopy(first_runtime), copy.deepcopy(first_brief), history())
        self.assertEqual(first_runtime, second_runtime)
        self.assertEqual(first_brief, second_brief)


if __name__ == "__main__":
    unittest.main()
