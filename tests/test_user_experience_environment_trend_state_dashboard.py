import unittest
from scripts.consolidate_user_experience_environment_trend import consolidate, enrich
from scripts.inject_user_experience_environment_trend_card import CARD_ID, inject, validate


class UserExperienceEnvironmentTrendStateDashboardTests(unittest.TestCase):
    def healthy(self):
        return {"status":"UX_ENV_TREND_STABLE","sample_count":3,"success_rate":100,"stable_sequence":3,"recurring_drift":False,"degradation_detected":False,"fingerprints":["a","a","a"]}

    def test_consolidates_eligible_state_and_preserves_readiness(self):
        state={"readiness":"unchanged","production_ready":False}; brief={}
        state, brief=enrich(state, brief, self.healthy())
        card=state["cards"]["user_experience_environment_trend"]
        self.assertTrue(card["eligible_for_human_review"])
        self.assertEqual("unchanged", state["readiness"])
        self.assertFalse(state["production_ready"])
        self.assertEqual(card, brief["indicators"]["user_experience_environment_trend"])

    def test_rejects_drift_and_degradation(self):
        trend=self.healthy(); trend["recurring_drift"]=True; trend["degradation_detected"]=True
        self.assertFalse(consolidate(trend)["eligible_for_human_review"])

    def test_dashboard_is_idempotent(self):
        state={"cards":{"user_experience_environment_trend":consolidate(self.healthy())}}
        dashboard={"cards":[]}; inject(state,dashboard); inject(state,dashboard)
        self.assertEqual(1, len([c for c in dashboard["cards"] if c["id"]==CARD_ID]))
        self.assertEqual([], validate(dashboard))

    def test_unsafe_eligibility_is_rejected(self):
        dashboard={"cards":[{"id":CARD_ID,"status":"UX_ENV_TREND_REVIEW","sample_count":1,"success_rate":50,"stable_sequence":0,"recurring_drift":True,"degradation_detected":True,"eligible_for_human_review":True,"mode":"report-only","production_blocker":False,"human_approval_required":True}]}
        self.assertGreaterEqual(len(validate(dashboard)), 5)


if __name__ == "__main__": unittest.main()
