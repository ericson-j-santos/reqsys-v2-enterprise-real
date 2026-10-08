from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "teams-commit-notification.yml"
RESOLVER = ROOT / "scripts" / "resolve_pc24x7_dev_locator.mjs"


class Pc24x7LocatorWatchContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.resolver = RESOLVER.read_text(encoding="utf-8")

    def test_monitor_is_scheduled_bounded_and_fail_closed(self) -> None:
        self.assertIn('cron: "*/10 * * * *"', self.workflow)
        self.assertIn("timeout-minutes: 5", self.workflow)
        self.assertIn('MIN_REMAINING_TTL_SECONDS: "300"', self.workflow)
        self.assertIn("watch-locator", self.workflow)
        self.assertIn("steps.locator.outputs.state != 'healthy'", self.workflow)
        self.assertIn("exit 1", self.workflow)

    def test_monitor_uses_signed_locator_and_sanitized_evidence(self) -> None:
        self.assertIn("resolve_pc24x7_dev_locator.mjs --self-test", self.workflow)
        self.assertIn("signed-locator.json", self.workflow)
        self.assertIn('"secrets_exposed": False', self.workflow)
        self.assertIn("actions/upload-artifact@", self.workflow)
        self.assertNotIn("continue-on-error:", self.workflow)
        self.assertNotIn("fly.dev", self.workflow)

    def test_alert_is_transition_based_and_uses_governed_fallback(self) -> None:
        self.assertIn("previous_conclusion", self.workflow)
        self.assertIn('transition="outage"', self.workflow)
        self.assertIn('transition="recovery"', self.workflow)
        self.assertIn("secrets.TEAMS_WEBHOOK_URL", self.workflow)
        self.assertIn("secrets.TEAMS_WEBHOOK_RECIPIENT", self.workflow)
        self.assertIn("teams_graph_gateway_autocontido.py", self.workflow)
        self.assertIn("pc24x7-dev-locator-alert", self.workflow)
        self.assertIn("pc24x7-dev-locator-recovery", self.workflow)
        self.assertIn("::add-mask::$TEAMS_WEBHOOK_URL", self.workflow)

    def test_resolver_exports_freshness_for_consumers(self) -> None:
        self.assertIn("issued_at=${result.issued_at}", self.resolver)
        self.assertIn("expires_at=${result.expires_at}", self.resolver)
        self.assertIn("remaining_ttl_seconds=", self.resolver)


if __name__ == "__main__":
    unittest.main(verbosity=2)
