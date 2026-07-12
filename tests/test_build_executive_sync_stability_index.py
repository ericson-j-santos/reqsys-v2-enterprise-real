import unittest

from scripts.build_executive_sync_stability_index import build_index, enrich


class ExecutiveSyncStabilityIndexTests(unittest.TestCase):
    def _history(self, count=20, passed=True, synchronized=True):
        sample = {"passed": passed, "synchronized": synchronized}
        return {
            "environments": {
                env: {"samples": [dict(sample, sequence=i) for i in range(count)]}
                for env in ("DEV", "STG", "PROD")
            }
        }

    def test_eligible_only_with_full_coverage_and_stability(self):
        index = build_index(self._history())
        self.assertEqual(index["status"], "eligible-for-human-review")
        self.assertTrue(index["eligible_for_human_review"])
        self.assertFalse(index["production_blocker"])
        self.assertEqual(index["mode"], "report-only")

    def test_incomplete_coverage_is_not_eligible(self):
        history = self._history()
        history["environments"]["PROD"]["samples"] = []
        index = build_index(history)
        self.assertEqual(index["status"], "insufficient-environment-coverage")
        self.assertFalse(index["eligible_for_human_review"])

    def test_degraded_environment_requires_attention(self):
        history = self._history()
        history["environments"]["STG"]["samples"][0]["synchronized"] = False
        history["environments"]["STG"]["samples"][1]["passed"] = False
        index = build_index(history)
        self.assertIn(index["status"], {"attention", "improving"})
        self.assertFalse(index["production_blocker"])

    def test_enrich_preserves_production_state_and_is_idempotent(self):
        runtime = {"production_ready": True, "cards": {}}
        brief = {"production_ready": True, "indicators": {}}
        index = build_index(self._history())
        first_runtime, first_brief = enrich(runtime, brief, index)
        second_runtime, second_brief = enrich(first_runtime, first_brief, index)
        self.assertTrue(second_runtime["production_ready"])
        self.assertTrue(second_brief["production_ready"])
        self.assertEqual(first_runtime, second_runtime)
        self.assertEqual(first_brief, second_brief)


if __name__ == "__main__":
    unittest.main()
