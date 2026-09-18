import unittest

from scripts.publish_user_experience_evidence_card import CARD_ID, publish
from scripts.smoke_user_experience_public_sync import validate_sync


SOURCE = {
    "score": 92,
    "status": "evidenced-and-consolidated",
    "evidenced": True,
    "consolidated": True,
    "scenarios": ["keyboard-focus", "mobile-navigation", "offline-online"],
    "workflow_run_id": 29287848346,
    "artifact": {"id": 8293879012, "expired": False},
    "mode": "report-only",
    "production_blocker": False,
    "human_approval_required": True,
}


class UserExperiencePublicSyncTests(unittest.TestCase):
    def test_publish_is_idempotent_and_preserves_guardrails(self):
        index = {"cards": {"user_experience_evidence": SOURCE}}
        dashboard = publish(index, {"cards": []})
        dashboard = publish(index, dashboard)
        cards = [card for card in dashboard["cards"] if card["id"] == CARD_ID]
        self.assertEqual(1, len(cards))
        self.assertEqual(92, cards[0]["score"])
        self.assertEqual("report-only", cards[0]["mode"])
        self.assertFalse(cards[0]["production_blocker"])
        self.assertTrue(cards[0]["human_approval_required"])

    def test_smoke_accepts_synchronized_contracts(self):
        state = {"cards": {"user_experience_evidence": SOURCE}}
        brief = {"indicators": {"user_experience_evidence": SOURCE}}
        dashboard = publish(state, {"cards": []})
        result = validate_sync(state, brief, dashboard)
        self.assertTrue(result["synchronized"])
        self.assertEqual("PUBLIC_UX_SYNC_OK", result["status"])
        self.assertTrue(result["fingerprint"])

    def test_smoke_detects_drift(self):
        state = {"cards": {"user_experience_evidence": SOURCE}}
        brief_source = dict(SOURCE, score=89)
        brief = {"indicators": {"user_experience_evidence": brief_source}}
        dashboard = publish(state, {"cards": []})
        result = validate_sync(state, brief, dashboard)
        self.assertFalse(result["synchronized"])
        self.assertEqual("PUBLIC_UX_SYNC_REVIEW", result["status"])

    def test_missing_evidence_uses_safe_fallback(self):
        dashboard = publish({"cards": {}}, {"cards": []})
        card = dashboard["cards"][0]
        self.assertEqual("collecting-evidence", card["status"])
        self.assertFalse(card["evidenced"])
        self.assertFalse(card["production_blocker"])


if __name__ == "__main__":
    unittest.main()
