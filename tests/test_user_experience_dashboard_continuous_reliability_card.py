import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inject = load("inject_continuous", "scripts/inject_user_experience_dashboard_continuous_reliability_card.py")
smoke = load("smoke_continuous", "scripts/smoke_user_experience_dashboard_continuous_reliability_card.py")


class ContinuousReliabilityCardTests(unittest.TestCase):
    def setUp(self):
        self.indicator = {
            "status": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_STABLE",
            "success_rate": 100.0,
            "stable_streak": 4,
            "samples": 4,
            "confidence_score": 100,
            "common_fingerprint": "abc",
            "recurrent_drift": False,
            "human_review_eligible": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }

    def test_injection_is_idempotent(self):
        first = inject.inject_card({"cards": []}, self.indicator)
        second = inject.inject_card(first, self.indicator)
        cards = [c for c in second["cards"] if c.get("id") == inject.CARD_ID]
        self.assertEqual(1, len(cards))

    def test_safe_fallback(self):
        card = inject.inject_card({}, None)["cards"][0]
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_RELIABILITY_REVIEW", card["status"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_smoke_ok(self):
        state = {"cards": {"user_experience_dashboard_continuous_reliability": self.indicator}}
        brief = {"indicators": {"user_experience_dashboard_continuous_reliability": self.indicator}}
        dashboard = inject.inject_card({"cards": []}, self.indicator)
        result = smoke.evaluate(state, brief, dashboard)
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK", result["classification"])

    def test_smoke_detects_drift(self):
        state = {"cards": {"user_experience_dashboard_continuous_reliability": self.indicator}}
        changed = dict(self.indicator, confidence_score=80)
        brief = {"indicators": {"user_experience_dashboard_continuous_reliability": changed}}
        dashboard = inject.inject_card({"cards": []}, self.indicator)
        result = smoke.evaluate(state, brief, dashboard)
        self.assertEqual("UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_REVIEW", result["classification"])


if __name__ == "__main__":
    unittest.main()
