import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.smoke_executive_sync_stability_index_public_smoke_trend_sync import append_history, validate


class ExecutiveSyncStabilityIndexPublicSmokeTrendSyncTest(unittest.TestCase):
    @patch("scripts.smoke_executive_sync_stability_index_public_smoke_trend_sync._get")
    def test_valid_public_contract_is_synchronized(self, get):
        card = {
            "trend": "stable",
            "coverage_complete": True,
            "synchronized": True,
            "total_samples": 9,
            "weighted_pass_rate_percent": 100.0,
            "minimum_stable_sequence": 3,
            "eligible_for_human_review": True,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }
        get.side_effect = [
            '<section id="executive_sync_stability_index_public_smoke_trend"></section>',
            json.dumps({"cards": {"executive_sync_stability_index_public_smoke_trend": card}}),
            json.dumps({"executive_sync_stability_index_public_smoke_trend": card}),
        ]
        result = validate("https://example.test", "dev")
        self.assertTrue(result["passed"])
        self.assertEqual("PUBLIC_TREND_SYNC_OK", result["status"])

    @patch("scripts.smoke_executive_sync_stability_index_public_smoke_trend_sync._get")
    def test_drift_becomes_review_without_blocking(self, get):
        runtime_card = {
            "trend": "stable", "coverage_complete": True, "synchronized": True,
            "total_samples": 9, "weighted_pass_rate_percent": 100.0,
            "minimum_stable_sequence": 3, "eligible_for_human_review": True,
            "mode": "report-only", "production_blocker": False,
            "human_approval_required": True,
        }
        brief_card = dict(runtime_card)
        brief_card["trend"] = "attention"
        get.side_effect = [
            '<section id="executive_sync_stability_index_public_smoke_trend"></section>',
            json.dumps({"cards": {"executive_sync_stability_index_public_smoke_trend": runtime_card}}),
            json.dumps({"executive_sync_stability_index_public_smoke_trend": brief_card}),
        ]
        result = validate("https://example.test", "prod")
        self.assertFalse(result["passed"])
        self.assertEqual("PUBLIC_TREND_SYNC_REVIEW", result["status"])
        self.assertFalse(result["production_blocker"])

    def test_history_is_idempotent_and_environment_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            sample = {"environment": "dev", "fingerprint": "abc", "status": "PUBLIC_TREND_SYNC_OK", "passed": True}
            append_history(path, sample)
            second = append_history(path, sample)
            self.assertEqual(1, len(second["samples"]))
            self.assertEqual(1, second["summary"]["sample_count"])
            third = append_history(path, {"environment": "stg", "fingerprint": "abc", "status": "PUBLIC_TREND_SYNC_OK", "passed": True})
            self.assertEqual(2, len(third["samples"]))
            self.assertEqual("stg", third["summary"]["environment"])


if __name__ == "__main__":
    unittest.main()
