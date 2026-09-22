import unittest

from scripts.enrich_executive_promotion_advisor_state import (
    enrich_brief,
    enrich_runtime,
    summarize,
)


class ExecutivePromotionAdvisorStateTests(unittest.TestCase):
    def advisor(self, decision="READY", confidence=96.5):
        return {
            "decision": decision,
            "confidence_percent": confidence,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
            "risk_domains": [] if decision == "READY" else ["runtime"],
            "recommendation": "review",
            "correlation_id": "corr-1",
            "generated_at": "2026-07-10T00:00:00+00:00",
            "inputs": {"runtime": "green"},
        }

    def test_summarize_ready(self):
        card = summarize(self.advisor())
        self.assertEqual(card["status"], "green")
        self.assertEqual(card["decision"], "READY")
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_summarize_review_and_hold(self):
        self.assertEqual(summarize(self.advisor("REVIEW"))["status"], "yellow")
        self.assertEqual(summarize(self.advisor("HOLD"))["status"], "red")

    def test_runtime_enrichment_is_idempotent_and_non_blocking(self):
        card = summarize(self.advisor("HOLD", 40))
        base = {"summary": {"production_ready": True}, "guardrails": []}
        first = enrich_runtime(base, card)
        second = enrich_runtime(first, card)
        self.assertEqual(first, second)
        self.assertTrue(second["summary"]["production_ready"])
        self.assertFalse(second["cards"]["executive_promotion_advisor"]["production_blocker"])
        self.assertEqual(second["guardrails"].count("executive_promotion_advisor_report_only"), 1)

    def test_brief_preserves_production_state(self):
        card = summarize(self.advisor("REVIEW", 70))
        brief = {"estado_producao": "ready", "semaforo_executivo": {"producao": "green"}}
        enriched = enrich_brief(brief, card)
        self.assertEqual(enriched["estado_producao"], "ready")
        self.assertEqual(enriched["semaforo_executivo"]["producao"], "green")
        self.assertEqual(enriched["semaforo_executivo"]["executive_promotion_advisor"], "yellow")
        self.assertIn("executive_promotion_advisor", enriched["evidencias"])


if __name__ == "__main__":
    unittest.main()
