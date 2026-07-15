from __future__ import annotations

import unittest
from copy import deepcopy

from scripts.build_user_experience_journey_quality import consolidate, evaluate
from scripts.smoke_user_experience_journey_quality import validate


class UserExperienceJourneyQualityTests(unittest.TestCase):
    def test_stable_journey(self) -> None:
        indicator = evaluate({
            "perceived_load_ms": 1200,
            "actionable_error_rate": 100,
            "empty_state_coverage": 100,
            "accessibility_score": 95,
            "feedback_coverage": 100,
        })
        self.assertEqual("UX_JOURNEY_QUALITY_STABLE", indicator["status"])
        self.assertGreaterEqual(indicator["quality_score"], 90)
        self.assertTrue(indicator["human_review_eligible"])

    def test_missing_evidence_is_safe(self) -> None:
        indicator = evaluate({})
        self.assertEqual("UX_JOURNEY_QUALITY_REVIEW", indicator["status"])
        self.assertFalse(indicator["evidence_complete"])
        self.assertFalse(indicator["production_blocker"])

    def test_slow_loading_reduces_score(self) -> None:
        indicator = evaluate({
            "perceived_load_ms": 5000,
            "actionable_error_rate": 100,
            "empty_state_coverage": 100,
            "accessibility_score": 100,
            "feedback_coverage": 100,
        })
        self.assertLess(indicator["quality_score"], 90)
        self.assertEqual("UX_JOURNEY_QUALITY_REVIEW", indicator["status"])

    def test_consolidation_is_idempotent_and_synchronized(self) -> None:
        indicator = evaluate({
            "perceived_load_ms": 1400,
            "actionable_error_rate": 100,
            "empty_state_coverage": 100,
            "accessibility_score": 100,
            "feedback_coverage": 100,
        })
        state, brief, dashboard = consolidate({}, {}, {"cards": []}, indicator)
        state, brief, dashboard = consolidate(state, brief, dashboard, indicator)
        self.assertEqual([], validate(state, brief, dashboard))
        self.assertEqual(1, len([card for card in dashboard["cards"] if card["id"] == indicator["id"]]))

    def test_smoke_detects_drift(self) -> None:
        indicator = evaluate({"perceived_load_ms": 1000, "actionable_error_rate": 100, "empty_state_coverage": 100, "accessibility_score": 100, "feedback_coverage": 100})
        state, brief, dashboard = consolidate({}, {}, {}, indicator)
        drifted_brief = deepcopy(brief)
        drifted_brief["indicators"]["user_experience_journey_quality"]["quality_score"] = 1
        self.assertTrue(any("drift" in error for error in validate(state, drifted_brief, dashboard)))


if __name__ == "__main__":
    unittest.main()
