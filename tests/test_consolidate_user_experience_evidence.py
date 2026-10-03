import unittest

from scripts.consolidate_user_experience_evidence import enrich, validate_evidence


class ConsolidateUserExperienceEvidenceTests(unittest.TestCase):
    def valid_evidence(self):
        return {
            "previous_score": 89,
            "conclusion": "success",
            "workflow_run_id": 29287848346,
            "workflow_url": "https://github.com/example/repo/actions/runs/29287848346",
            "scenarios": ["keyboard_focus", "mobile_navigation", "offline_recovery"],
            "artifact": {
                "id": 8293879012,
                "name": "ux-evidence-sha",
                "size_in_bytes": 643924,
                "digest": "sha256:ccf1c1cd72abac1708cedcc2bfc035610a5529a001d7714e9a2a874eee59fe60",
                "expired": False,
                "expires_at": "2026-10-11T21:51:01Z",
            },
        }

    def test_marks_92_as_evidenced_with_complete_evidence(self):
        result = validate_evidence(self.valid_evidence())
        self.assertTrue(result["evidenced"])
        self.assertEqual(result["status"], "evidenced")
        self.assertEqual(result["score"], 92)
        self.assertEqual(result["previous_score"], 89)

    def test_does_not_promote_score_when_artifact_is_expired(self):
        evidence = self.valid_evidence()
        evidence["artifact"]["expired"] = True
        result = validate_evidence(evidence)
        self.assertFalse(result["evidenced"])
        self.assertIsNone(result["score"])
        self.assertFalse(result["checks"]["artifact_available"])

    def test_does_not_promote_score_when_scenario_is_missing(self):
        evidence = self.valid_evidence()
        evidence["scenarios"] = ["keyboard_focus", "mobile_navigation"]
        result = validate_evidence(evidence)
        self.assertFalse(result["evidenced"])
        self.assertFalse(result["checks"]["required_scenarios"])

    def test_enriches_state_and_brief_without_changing_production_flags(self):
        state = {"production_ready": False, "readiness": "review", "executive_indicators": {"user_experience": 89}}
        brief = {"production_ready": False, "executive_indicators": {"user_experience": 89}}
        result = validate_evidence(self.valid_evidence())

        state_out, brief_out = enrich(state, brief, result)

        self.assertEqual(state_out["executive_indicators"]["user_experience"], 92)
        self.assertEqual(brief_out["executive_indicators"]["user_experience"], 92)
        self.assertFalse(state_out["production_ready"])
        self.assertEqual(state_out["readiness"], "review")
        self.assertFalse(brief_out["production_ready"])
        self.assertTrue(state_out["cards"]["user_experience_evidence"]["human_approval_required"])
        self.assertFalse(state_out["cards"]["user_experience_evidence"]["production_blocker"])

    def test_is_idempotent(self):
        result = validate_evidence(self.valid_evidence())
        state_once, brief_once = enrich({}, {}, result)
        state_twice, brief_twice = enrich(state_once, brief_once, result)
        self.assertEqual(state_once, state_twice)
        self.assertEqual(brief_once, brief_twice)


if __name__ == "__main__":
    unittest.main()
