import unittest

from scripts.inject_user_experience_sync_confidence_card import CARD_ID, inject
from scripts.smoke_user_experience_sync_confidence_card import validate


class SyncConfidenceDashboardTests(unittest.TestCase):
    def sample(self):
        return {
            "status": "UX_SYNC_CONFIDENCE_STABLE",
            "confidence_level": "HIGH",
            "confidence_score": 100,
            "sample_count": 3,
            "sync_rate": 100.0,
            "stable_sequence": 3,
            "recurrent_drift": False,
            "human_review_eligible": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }

    def test_publicacao_idempotente(self):
        brief = {"indicators": {"user_experience_sync_confidence": self.sample()}}
        first = inject({"cards": []}, brief)
        second = inject(first, brief)
        cards = [card for card in second["cards"] if card["id"] == CARD_ID]
        self.assertEqual(1, len(cards))
        self.assertEqual(100, cards[0]["confidence_score"])

    def test_fallback_seguro(self):
        dashboard = inject({"cards": []}, {"indicators": {}})
        card = next(card for card in dashboard["cards"] if card["id"] == CARD_ID)
        self.assertEqual("LOW", card["confidence_level"])
        self.assertFalse(card["human_review_eligible"])

    def test_smoke_sincronizado(self):
        value = self.sample()
        state = {"cards": {"user_experience_sync_confidence": value}}
        brief = {"indicators": {"user_experience_sync_confidence": value}}
        dashboard = inject({"cards": []}, brief)
        result = validate(state, brief, dashboard)
        self.assertTrue(result["synchronized"])
        self.assertEqual("UX_SYNC_CONFIDENCE_CARD_OK", result["status"])

    def test_smoke_detecta_drift(self):
        value = self.sample()
        state = {"cards": {"user_experience_sync_confidence": value}}
        brief = {"indicators": {"user_experience_sync_confidence": value}}
        dashboard = inject({"cards": []}, brief)
        dashboard["cards"][0]["confidence_score"] = 80
        result = validate(state, brief, dashboard)
        self.assertFalse(result["synchronized"])
        self.assertEqual("UX_SYNC_CONFIDENCE_CARD_REVIEW", result["status"])


if __name__ == "__main__":
    unittest.main()
