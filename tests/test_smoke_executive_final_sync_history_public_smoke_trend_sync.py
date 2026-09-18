import unittest

from scripts.smoke_executive_final_sync_history_public_smoke_trend_sync import evaluate, update_history


class FinalTrendSyncSmokeTests(unittest.TestCase):
    def payloads(self):
        card = {
            "status": "eligible-for-human-review",
            "environment_coverage": {"dev": True, "stg": True, "prod": True},
            "sample_count": 9,
            "weighted_pass_rate": 1.0,
            "minimum_stable_sequence": 3,
            "synchronized": True,
            "common_fingerprint": "abc",
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }
        return {"cards": {"executive_final_sync_history_public_smoke_trend": card}}, {"indicators": {"executive_final_sync_history_public_smoke_trend": dict(card)}}

    def test_sync_ok(self):
        runtime, brief = self.payloads()
        result = evaluate('<section id="executive-final-sync-history-public-smoke-trend"></section>', runtime, brief, "dev")
        self.assertEqual("PUBLIC_FINAL_TREND_SYNC_OK", result["status"])
        self.assertEqual([], result["issues"])

    def test_detects_drift(self):
        runtime, brief = self.payloads()
        brief["indicators"]["executive_final_sync_history_public_smoke_trend"]["sample_count"] = 8
        result = evaluate('<section id="executive-final-sync-history-public-smoke-trend"></section>', runtime, brief, "stg")
        self.assertIn("runtime_brief_drift", result["issues"])

    def test_detects_missing_or_duplicate_card(self):
        runtime, brief = self.payloads()
        result = evaluate("", runtime, brief, "prod")
        self.assertIn("public_card_presence", result["issues"])

    def test_history_is_idempotent_and_bounded(self):
        runtime, brief = self.payloads()
        evidence = evaluate('<section id="executive-final-sync-history-public-smoke-trend"></section>', runtime, brief, "dev")
        history = update_history({}, evidence)
        history = update_history(history, evidence)
        self.assertEqual(1, len(history["samples"]))

    def test_unsafe_guardrail_requires_review(self):
        runtime, brief = self.payloads()
        runtime["cards"]["executive_final_sync_history_public_smoke_trend"]["production_blocker"] = True
        result = evaluate('<section id="executive-final-sync-history-public-smoke-trend"></section>', runtime, brief, "dev")
        self.assertIn("unsafe_production_blocker", result["issues"])


if __name__ == "__main__":
    unittest.main()
