import copy
import unittest

from scripts.consolidate_user_experience_environment_history import build_card, consolidate


class UserExperienceEnvironmentHistoryTests(unittest.TestCase):
    def valid_history(self):
        environments = {
            env: {"pass_rate": 100, "fingerprint": "sha256:abc"}
            for env in ("DEV", "STG", "PROD")
        }
        return {"environments": environments, "drift_detected": False, "stable_sequence": 3}

    def test_builds_eligible_card(self):
        card = build_card(self.valid_history())
        self.assertEqual("eligible-for-human-review", card["status"])
        self.assertEqual(100, card["minimum_pass_rate"])
        self.assertEqual("sha256:abc", card["common_fingerprint"])
        self.assertTrue(card["eligible_for_human_review"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_drift_keeps_safe_state(self):
        history = self.valid_history()
        history["environments"]["PROD"]["fingerprint"] = "sha256:different"
        card = build_card(history)
        self.assertEqual("collecting-evidence", card["status"])
        self.assertTrue(card["drift_detected"])
        self.assertFalse(card["eligible_for_human_review"])

    def test_incomplete_coverage_is_not_eligible(self):
        history = self.valid_history()
        del history["environments"]["PROD"]
        card = build_card(history)
        self.assertFalse(card["eligible_for_human_review"])
        self.assertNotEqual({"DEV", "STG", "PROD"}, set(card["environment_coverage"]))

    def test_consolidation_is_idempotent_and_preserves_readiness(self):
        history = self.valid_history()
        state = {"readiness": {"status": "unchanged"}, "cards": {}}
        brief = {"production_ready": False, "indicators": {}}
        first_state, first_brief = consolidate(history, copy.deepcopy(state), copy.deepcopy(brief))
        second_state, second_brief = consolidate(history, first_state, first_brief)
        self.assertEqual(first_state, second_state)
        self.assertEqual(first_brief, second_brief)
        self.assertEqual({"status": "unchanged"}, second_state["readiness"])
        self.assertFalse(second_brief["production_ready"])


if __name__ == "__main__":
    unittest.main()
