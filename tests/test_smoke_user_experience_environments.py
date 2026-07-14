import unittest
from unittest.mock import patch

from scripts.smoke_user_experience_environments import collect


class UserExperienceEnvironmentSmokeTests(unittest.TestCase):
    @patch("scripts.smoke_user_experience_environments.probe")
    def test_complete_consistent_environments_are_ok(self, mocked_probe):
        mocked_probe.return_value = {"status": 200, "ok": True, "latency_ms": 10.0, "body_sha256": "a" * 64}
        report = collect({"DEV": "https://dev", "STG": "https://stg", "PROD": "https://prod"})
        self.assertTrue(report["complete"])
        self.assertFalse(report["drift_detected"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_OK", report["status"])
        self.assertEqual("report-only", report["mode"])
        self.assertFalse(report["production_blocker"])
        self.assertTrue(report["human_approval_required"])

    @patch("scripts.smoke_user_experience_environments.probe")
    def test_failure_requires_review_without_blocking_production(self, mocked_probe):
        mocked_probe.side_effect = [
            {"status": 200, "ok": True, "latency_ms": 1.0, "body_sha256": "a" * 64},
            {"status": 503, "ok": False, "latency_ms": 1.0, "body_sha256": "b" * 64},
        ] * 6
        report = collect({"DEV": "https://dev", "STG": "https://stg", "PROD": "https://prod"})
        self.assertFalse(report["complete"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_REVIEW", report["status"])
        self.assertFalse(report["production_blocker"])

    @patch("scripts.smoke_user_experience_environments.probe")
    def test_different_contracts_detect_drift(self, mocked_probe):
        calls = {"n": 0}
        def fake_probe(url, timeout):
            calls["n"] += 1
            status = 204 if calls["n"] > 4 else 200
            return {"status": status, "ok": True, "latency_ms": 1.0, "body_sha256": str(status)}
        mocked_probe.side_effect = fake_probe
        report = collect({"DEV": "https://dev", "STG": "https://stg"})
        self.assertTrue(report["drift_detected"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_REVIEW", report["status"])


if __name__ == "__main__":
    unittest.main()
