import json
import unittest
from unittest.mock import patch

from scripts.smoke_executive_promotion_advisor_public_url import smoke


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
    def test_homologates_public_contract(self, fetch_text):
        fetch_text.side_effect = self.responses()
        evidence = smoke("https://example.test", "dev")
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["decision"], "HOMOLOGATED")
        self.assertEqual(evidence["environment"], "dev")

    @patch("scripts.smoke_executive_promotion_advisor_public_url.fetch_text")
    def test_blocks_automatic_production_blocking(self, fetch_text):
        html, contract = self.responses()
        payload = json.loads(contract)
        payload["cards"]["executive_promotion_advisor"]["production_blocker"] = True
        fetch_text.side_effect = [html, json.dumps(payload)]
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


if __name__ == "__main__":
    unittest.main()
