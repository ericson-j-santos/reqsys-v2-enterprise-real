import copy
import unittest

from scripts.enrich_executive_promotion_advisor_homologation_trend import (
    enrich_executive_brief,
    enrich_runtime_index,
    summarize,
)


class ExecutivePromotionAdvisorHomologationTrendTests(unittest.TestCase):
    def history(self, **overrides):
        summary = {
            "sample_count": 30,
            "artifact_pass_rate_percent": 100,
            "public_pass_rate_percent": 100,
            "full_homologation_rate_percent": 100,
            "stable_streak": 20,
            "latest_decision": "HOMOLOGATED",
            "eligible_for_gate_review": True,
            "production_blocker": False,
        }
        summary.update(overrides)
        return {
            "schema_version": "1.0.0",
            "generated_at": "2026-07-11T12:00:00+00:00",
            "mode": "report-only",
            "summary": summary,
            "entries": [],
        }

    def test_ready_history_is_only_eligible_for_human_review(self):
        trend = summarize(self.history())
        self.assertEqual("eligible-for-human-review", trend["trend"])
        self.assertTrue(trend["eligible_for_gate_review"])
        self.assertFalse(trend["production_blocker"])
        self.assertTrue(trend["human_approval_required"])

    def test_insufficient_history_never_implies_gate_promotion(self):
        trend = summarize(self.history(
            sample_count=1,
            full_homologation_rate_percent=100,
            stable_streak=1,
            eligible_for_gate_review=False,
        ))
        self.assertFalse(trend["eligible_for_gate_review"])
        self.assertEqual("stable", trend["trend"])
        self.assertEqual("report-only", trend["mode"])

    def test_runtime_and_brief_enrichment_are_idempotent(self):
        trend = summarize(self.history())
        runtime = {
            "summary": {"production_ready": False},
            "cards": {},
            "links": {},
            "guardrails": [],
        }
        brief = {
            "indicadores": {"production_ready": False},
            "semaforo_executivo": {},
            "evidencias": {},
        }

        runtime_once = enrich_runtime_index(copy.deepcopy(runtime), trend)
        runtime_twice = enrich_runtime_index(copy.deepcopy(runtime_once), trend)
        brief_once = enrich_executive_brief(copy.deepcopy(brief), trend)
        brief_twice = enrich_executive_brief(copy.deepcopy(brief_once), trend)

        self.assertEqual(runtime_once, runtime_twice)
        self.assertEqual(brief_once, brief_twice)
        self.assertFalse(runtime_twice["summary"]["production_ready"])
        self.assertFalse(brief_twice["indicadores"]["production_ready"])
        self.assertEqual(
            1,
            runtime_twice["guardrails"].count(
                "executive_promotion_advisor_homologation_trend_report_only"
            ),
        )

    def test_attention_history_is_visible_but_non_blocking(self):
        trend = summarize(self.history(
            sample_count=10,
            full_homologation_rate_percent=70,
            stable_streak=0,
            eligible_for_gate_review=False,
            latest_decision="REVIEW",
        ))
        runtime = enrich_runtime_index({"summary": {}, "cards": {}}, trend)
        brief = enrich_executive_brief({}, trend)

        card = runtime["cards"]["executive_promotion_advisor_homologation_trend"]
        self.assertEqual("attention", card["trend"])
        self.assertFalse(card["production_blocker"])
        self.assertEqual(
            "red",
            brief["semaforo_executivo"]["executive_promotion_advisor_homologation_trend"],
        )


if __name__ == "__main__":
    unittest.main()
