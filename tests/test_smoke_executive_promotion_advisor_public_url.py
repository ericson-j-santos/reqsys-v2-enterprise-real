import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from scripts.smoke_executive_promotion_advisor_public_url import fetch_text, smoke


class ExecutivePromotionAdvisorPublicSmokeTests(unittest.TestCase):
    def responses(self):
        html = '<section id="executive-promotion-advisor-card"></section><script>renderExecutivePromotionAdvisor(payload);</script>'
        contract = json.dumps({
            "cards": {
                "executive_promotion_advisor": {
                    "decision": "REVIEW",
                    "confidence_percent": 70,
                    "risk_domains": ["runtime"],
                    "mode": "report-only",
                    "production_blocker": False,
                    "human_approval_required": True,
                }
            }
        })
        return [html, contract]

    @patch("scripts.smoke_executive_promotion_advisor_public_url.fetch_text")
    def test_homologates_public_contract(self, fetch_text_mock):
        fetch_text_mock.side_effect = self.responses()
        evidence = smoke("https://example.test", "dev")
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["decision"], "HOMOLOGATED")
        self.assertEqual(evidence["environment"], "dev")

    @patch("scripts.smoke_executive_promotion_advisor_public_url.fetch_text")
    def test_blocks_automatic_production_blocking(self, fetch_text_mock):
        html, contract = self.responses()
        payload = json.loads(contract)
        payload["cards"]["executive_promotion_advisor"]["production_blocker"] = True
        fetch_text_mock.side_effect = [html, json.dumps(payload)]
        evidence = smoke("https://example.test", "prod")
        self.assertEqual(evidence["status"], "failed")
        self.assertIn("production_blocker_disabled", evidence["errors"])

    @patch("scripts.smoke_executive_promotion_advisor_public_url.fetch_text")
    def test_resolves_github_pages_ops_dashboard_paths(self, fetch_text):
        fetch_text.side_effect = self.responses()
        evidence = smoke("https://example.test/project/", "github-pages")

        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(
            evidence["resolved_urls"]["dashboard"],
            "https://example.test/project/ops-dashboard/",
        )
        self.assertEqual(
            evidence["resolved_urls"]["contract"],
            "https://example.test/project/ops-dashboard/data/runtime-executive-index.json",
        )
        self.assertEqual(
            [call.args[0] for call in fetch_text.call_args_list],
            [
                "https://example.test/project/ops-dashboard/",
                "https://example.test/project/ops-dashboard/data/runtime-executive-index.json",
            ],
        )

    @patch("scripts.smoke_executive_promotion_advisor_public_url.time.sleep")
    @patch("scripts.smoke_executive_promotion_advisor_public_url.urllib.request.urlopen")
    def test_retries_transient_publication_failure(self, urlopen_mock, sleep_mock):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"published"
        urlopen_mock.side_effect = [urllib.error.URLError("temporary unavailability"), response]

        content = fetch_text(
            "https://example.test/data/runtime-executive-index.json",
            timeout=1.0,
            attempts=2,
            retry_delay=0.01,
        )

        self.assertEqual(content, "published")
        self.assertEqual(urlopen_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.01)

    def test_rejects_invalid_retry_configuration(self):
        with self.assertRaises(ValueError):
            fetch_text("https://example.test", attempts=0)
        with self.assertRaises(ValueError):
            fetch_text("https://example.test", retry_delay=-1)


if __name__ == "__main__":
    unittest.main()
