from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "teams-commit-notification.yml"


class TeamsCommitNotificationFallbackContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_gateway_assinado_permanece_rota_primaria(self) -> None:
        self.assertIn("resolve_pc24x7_dev_locator.mjs --self-test", self.text)
        self.assertIn("steps.locator.outputs.base_url", self.text)
        self.assertIn('delivery_mode=gateway', self.text)
        self.assertIn('"scripts/notificar_teams.py"', self.text)
        self.assertIn('"flow_bot"', self.text)
        self.assertIn('"--strict"', self.text)
        self.assertNotIn("vars.TEAMS_GATEWAY_BASE_URL", self.text)
        self.assertNotIn("fly.io", self.text)
        self.assertNotIn("fly.dev", self.text)

    def test_webhook_governado_e_fallback_pre_envio(self) -> None:
        self.assertIn("locator_rc=$?", self.text)
        self.assertIn('echo "resolved=false"', self.text)
        self.assertIn("if: steps.locator.outputs.resolved == 'true'", self.text)
        self.assertIn("TEAMS_WEBHOOK_URL: ${{ secrets.TEAMS_WEBHOOK_URL }}", self.text)
        self.assertIn("TEAMS_WEBHOOK_RECIPIENT: ${{ secrets.TEAMS_WEBHOOK_RECIPIENT }}", self.text)
        self.assertIn('elif [[ "$LOCATOR_RESOLVED" != "true"', self.text)
        self.assertIn('delivery_mode=webhook_fallback', self.text)
        self.assertIn('if delivery_mode == "gateway"', self.text)
        self.assertIn('"tools/geradores/teams_graph_gateway_autocontido.py"', self.text)
        self.assertIn('"send-webhook"', self.text)
        self.assertIn('"--adaptive-card-file"', self.text)
        self.assertIn('"commit-notification-fallback"', self.text)

    def test_dupla_indisponibilidade_permanece_fail_closed(self) -> None:
        self.assertIn('delivery_mode=unavailable', self.text)
        self.assertIn("Nenhuma rota Teams governada disponível", self.text)
        self.assertIn("Teams não confirmou envio pela rota", self.text)
        self.assertIn('output.write(f"delivery_route={delivery_mode}\\n")', self.text)
        self.assertNotIn("continue-on-error:", self.text)
        self.assertNotIn("concurrency:", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
