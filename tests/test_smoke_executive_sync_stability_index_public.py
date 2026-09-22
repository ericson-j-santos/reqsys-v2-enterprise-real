import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.smoke_executive_sync_stability_index_public import append_history, validate


class ExecutiveSyncStabilityIndexPublicSmokeTest(unittest.TestCase):
    @patch("scripts.smoke_executive_sync_stability_index_public._get")
    def test_valid_contract(self, get):
        get.side_effect = [
            '<section id="executive_sync_stability_index"></section>',
            json.dumps({"cards": {"executive_sync_stability_index": {
                "mode": "report-only",
                "production_blocker": False,
                "human_approval_required": True,
            }}}),
        ]
        result = validate("https://example.test", "dev")
        self.assertTrue(result["passed"])
        self.assertEqual("PUBLIC_INDEX_SMOKE_OK", result["status"])

    @patch("scripts.smoke_executive_sync_stability_index_public._get")
    def test_unsafe_contract_becomes_review(self, get):
        get.side_effect = [
            '<section id="executive_sync_stability_index"></section>',
            json.dumps({"cards": {"executive_sync_stability_index": {
                "mode": "blocking",
                "production_blocker": True,
                "human_approval_required": False,
            }}}),
        ]
        result = validate("https://example.test", "prod")
        self.assertFalse(result["passed"])
        self.assertEqual("PUBLIC_INDEX_SMOKE_REVIEW", result["status"])
        self.assertFalse(result["production_blocker"])

    def test_history_is_idempotent_and_environment_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            sample = {"environment": "dev", "fingerprint": "abc", "passed": True}
            first = append_history(path, sample)
            second = append_history(path, sample)
            self.assertEqual(1, len(second["samples"]))
            self.assertEqual(1, second["summary"]["sample_count"])
            stg = append_history(path, {"environment": "stg", "fingerprint": "xyz", "passed": True})
            self.assertEqual(2, len(stg["samples"]))
            self.assertEqual("stg", stg["summary"]["environment"])


if __name__ == "__main__":
    unittest.main()
