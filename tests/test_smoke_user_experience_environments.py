import unittest
from unittest.mock import patch

from scripts.smoke_user_experience_environments import REQUIRED_PATHS, collect, default_environments


class UserExperienceEnvironmentSmokeTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_default_dev_runtime_fails_closed_without_locator(self):
        with self.assertRaisesRegex(ValueError, "REQSYS_DEV_BASE_URL_missing"):
            default_environments()

    @patch.dict("os.environ", {"REQSYS_DEV_BASE_URL": "https://reqsys-app-dev.fly.dev"}, clear=True)
    def test_default_dev_runtime_rejects_fly(self):
        with self.assertRaisesRegex(ValueError, "legacy_fly_dev_runtime_forbidden"):
            default_environments()

    @patch.dict("os.environ", {"REQSYS_DEV_BASE_URL": "https://pc24x7.trycloudflare.com"}, clear=True)
    def test_default_dev_runtime_accepts_pc24x7(self):
        self.assertEqual("https://pc24x7.trycloudflare.com", default_environments()["DEV"])

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
        self.assertFalse(report["automatic_score_promotion"])
        self.assertIn("/estatisticas/total-requisitos", report["required_paths"])
        self.assertTrue(all(item["indicator_drilldown_available"] for item in report["environments"].values()))
        self.assertEqual(len(REQUIRED_PATHS) * 3, mocked_probe.call_count)

    @patch("scripts.smoke_user_experience_environments.probe")
    def test_failure_requires_review_without_blocking_production(self, mocked_probe):
        respostas_por_ambiente = [
            {"status": 200, "ok": True, "latency_ms": 1.0, "body_sha256": "a" * 64},
            {"status": 503, "ok": False, "latency_ms": 1.0, "body_sha256": "b" * 64},
            {"status": 200, "ok": True, "latency_ms": 1.0, "body_sha256": "c" * 64},
            {"status": 200, "ok": True, "latency_ms": 1.0, "body_sha256": "d" * 64},
            {"status": 200, "ok": True, "latency_ms": 1.0, "body_sha256": "e" * 64},
        ]
        mocked_probe.side_effect = respostas_por_ambiente * 3
        report = collect({"DEV": "https://dev", "STG": "https://stg", "PROD": "https://prod"})
        self.assertFalse(report["complete"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_REVIEW", report["status"])
        self.assertFalse(report["production_blocker"])

    @patch("scripts.smoke_user_experience_environments.probe")
    def test_different_contracts_detect_drift(self, mocked_probe):
        calls = {"n": 0}

        def fake_probe(url, timeout):
            calls["n"] += 1
            status = 204 if calls["n"] > len(REQUIRED_PATHS) else 200
            return {"status": status, "ok": True, "latency_ms": 1.0, "body_sha256": str(status)}

        mocked_probe.side_effect = fake_probe
        report = collect({"DEV": "https://dev", "STG": "https://stg"})
        self.assertTrue(report["drift_detected"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_REVIEW", report["status"])

    @patch("scripts.smoke_user_experience_environments.probe")
    def test_drilldown_indisponivel_fica_evidenciado_sem_promover_score(self, mocked_probe):
        def fake_probe(url, timeout):
            disponivel = not url.endswith("/estatisticas/total-requisitos")
            return {
                "status": 200 if disponivel else 404,
                "ok": disponivel,
                "latency_ms": 1.0,
                "body_sha256": "a" * 64,
            }

        mocked_probe.side_effect = fake_probe
        report = collect({"DEV": "https://dev"})
        self.assertFalse(report["environments"]["DEV"]["indicator_drilldown_available"])
        self.assertEqual("PUBLIC_UX_ENV_SYNC_REVIEW", report["status"])
        self.assertFalse(report["automatic_score_promotion"])


if __name__ == "__main__":
    unittest.main()
