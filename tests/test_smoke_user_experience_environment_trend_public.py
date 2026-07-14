import unittest
from unittest.mock import patch

from scripts.smoke_user_experience_environment_trend_public import build_report


class PublicUxTrendSmokeTests(unittest.TestCase):
    @patch("scripts.smoke_user_experience_environment_trend_public.fetch")
    def test_healthy_environments_are_ok(self, fetch):
        fetch.return_value = {"ok": True, "status": 200, "body": {"status": "ok"}}
        report = build_report({"dev": "https://dev", "stg": "https://stg", "prod": "https://prod"})
        self.assertEqual("UX_ENV_TREND_PUBLIC_OK", report["status"])
        self.assertEqual(100, report["availability_rate"])
        self.assertFalse(report["drift_detected"])
        self.assertFalse(report["production_blocker"])
        self.assertTrue(report["human_approval_required"])

    @patch("scripts.smoke_user_experience_environment_trend_public.fetch")
    def test_failure_requires_review(self, fetch):
        fetch.side_effect = lambda url: ({"ok": False, "status": 503, "body": {}} if "stg" in url else {"ok": True, "status": 200, "body": {}})
        report = build_report({"dev": "https://dev", "stg": "https://stg", "prod": "https://prod"})
        self.assertEqual("UX_ENV_TREND_PUBLIC_REVIEW", report["status"])
        self.assertLess(report["availability_rate"], 100)


if __name__ == "__main__":
    unittest.main()
