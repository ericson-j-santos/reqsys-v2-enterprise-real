import json
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_NAME = "teams_graph_gateway_autocontido"
MODULE_PATH = Path(__file__).parents[1] / "tools" / "geradores" / "teams_graph_gateway_autocontido.py"
spec = spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert spec and spec.loader
module = module_from_spec(spec)
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)


class TeamsGraphGatewayAutocontidoTest(unittest.TestCase):
    def setUp(self):
        self.config = module.GatewayConfig(
            webhook_url="https://example.invalid/hook",
            webhook_recipient="pessoa@example.invalid",
        )
        self.card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.5",
            "body": [{"type": "TextBlock", "text": "ReqSys", "wrap": True}],
        }

    def test_safe_json_aceita_resposta_textual_do_teams(self):
        self.assertEqual(module.HttpClient.safe_json("1"), {"value": 1})
        self.assertEqual(module.HttpClient.safe_json("Accepted"), {"message": "Accepted"})
        self.assertEqual(module.HttpClient.safe_json(""), {})

    def test_webhook_dry_run_gera_evidencia_sem_rede(self):
        result = module.TeamsGateway(self.config).send_webhook("commit abc123", "ReqSys", dry_run=True)

        self.assertTrue(result.success)
        self.assertEqual(result.route, "webhook")
        self.assertTrue(result.correlation_id)
        self.assertTrue(result.response["planned"])
        self.assertEqual(result.response["payload"]["to"], "pessoa@example.invalid")

    def test_webhook_adaptive_card_preserva_fallback_e_contrato(self):
        result = module.TeamsGateway(self.config).send_webhook(
            "fallback markdown",
            "ReqSys",
            dry_run=True,
            adaptive_card=self.card,
        )

        payload = result.response["payload"]
        self.assertEqual(payload["content"], "fallback markdown")
        self.assertEqual(payload["renderMode"], "adaptive-card")
        self.assertEqual(payload["adaptiveCard"]["version"], "1.5")
        self.assertEqual(json.loads(payload["adaptiveCardJson"]), self.card)

    def test_load_adaptive_card_por_arquivo(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as stream:
            json.dump(self.card, stream)
            path = stream.name
        try:
            self.assertEqual(module.load_adaptive_card(path), self.card)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_adaptive_card_invalido_falha_antes_da_rede(self):
        invalid = {"type": "MessageCard", "body": []}
        with self.assertRaises(module.GatewayError) as context:
            module.TeamsGateway(self.config).send_webhook(
                "mensagem",
                "ReqSys",
                dry_run=True,
                adaptive_card=invalid,
            )
        self.assertIn("type=AdaptiveCard", str(context.exception))

    def test_webhook_exige_configuracao(self):
        gateway = module.TeamsGateway(module.GatewayConfig())

        with self.assertRaises(module.GatewayError) as context:
            gateway.send_webhook("mensagem", "ReqSys")
        self.assertIn("TEAMS_WEBHOOK_URL", str(context.exception))

    def test_webhook_exige_destinatario_valido(self):
        config = module.GatewayConfig(webhook_url="https://example.invalid/hook")
        gateway = module.TeamsGateway(config)

        with self.assertRaises(module.GatewayError) as context:
            gateway.send_webhook("mensagem", "ReqSys", dry_run=True)
        self.assertIn("TEAMS_WEBHOOK_RECIPIENT", str(context.exception))

        config_sem_arroba = module.GatewayConfig(
            webhook_url="https://example.invalid/hook",
            webhook_recipient="Canal ReqSys - Commits",
        )
        with self.assertRaises(module.GatewayError):
            module.TeamsGateway(config_sem_arroba).send_webhook("mensagem", "ReqSys", dry_run=True)

    def test_webhook_payload_declara_event_type_padrao_de_commit(self):
        result = module.TeamsGateway(self.config).send_webhook("commit abc123", "ReqSys", dry_run=True)
        self.assertEqual(result.response["payload"]["eventType"], "commit-notification")

    def test_webhook_permite_event_type_explicito(self):
        result = module.TeamsGateway(self.config).send_webhook(
            "mensagem", "ReqSys", dry_run=True, event_type="canario-semanal"
        )
        self.assertEqual(result.response["payload"]["eventType"], "canario-semanal")

    def test_webhook_rejeita_event_type_vazio(self):
        with self.assertRaises(module.GatewayError) as context:
            module.TeamsGateway(self.config).send_webhook("mensagem", "ReqSys", dry_run=True, event_type="  ")
        self.assertIn("event_type", str(context.exception))

    def test_contrato_aceita_resposta_do_flow_real_sem_echo(self):
        """O robo_envia_teamsv2 hoje responde {ok, to, titleLength, ...},
        sem ecoar correlationId/eventType — o contrato deve tolerar isso."""
        module.TeamsGateway._validar_contrato_resposta(
            {"ok": True, "to": "pessoa@example.invalid", "titleLength": 10},
            correlation_id="abc-123",
            event_type="commit-notification",
        )

    def test_contrato_rejeita_correlation_id_divergente(self):
        with self.assertRaises(module.GatewayError) as context:
            module.TeamsGateway._validar_contrato_resposta(
                {"correlationId": "outro-id"},
                correlation_id="abc-123",
                event_type="commit-notification",
            )
        self.assertIn("correlationId", str(context.exception))

    def test_contrato_rejeita_event_type_divergente(self):
        with self.assertRaises(module.GatewayError) as context:
            module.TeamsGateway._validar_contrato_resposta(
                {"eventType": "requirement"},
                correlation_id="abc-123",
                event_type="commit-notification",
            )
        self.assertIn("eventType", str(context.exception))

    def test_webhook_real_com_resposta_divergente_falha_end_to_end(self):
        class HttpFalsoComRespostaErrada:
            def request(self, method, url, *, headers=None, payload=None, form=None):
                return 200, {"correlationId": "id-de-outro-fluxo", "type": "requirement"}

        gateway = module.TeamsGateway(self.config, http=HttpFalsoComRespostaErrada())
        with self.assertRaises(module.GatewayError) as context:
            gateway.send_webhook("commit abc123", "ReqSys")
        self.assertIn("Contrato violado", str(context.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
