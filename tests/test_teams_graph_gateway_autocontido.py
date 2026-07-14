import sys
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
    def test_safe_json_aceita_resposta_textual_do_teams(self):
        self.assertEqual(module.HttpClient.safe_json("1"), {"value": 1})
        self.assertEqual(module.HttpClient.safe_json("Accepted"), {"message": "Accepted"})
        self.assertEqual(module.HttpClient.safe_json(""), {})

    def test_webhook_dry_run_gera_evidencia_sem_rede(self):
        config = module.GatewayConfig(webhook_url="https://example.invalid/hook")
        result = module.TeamsGateway(config).send_webhook("commit abc123", "ReqSys", dry_run=True)

        self.assertTrue(result.success)
        self.assertEqual(result.route, "webhook")
        self.assertTrue(result.correlation_id)
        self.assertTrue(result.response["planned"])

    def test_webhook_exige_configuracao(self):
        gateway = module.TeamsGateway(module.GatewayConfig())

        with self.assertRaises(module.GatewayError) as context:
            gateway.send_webhook("mensagem", "ReqSys")
        self.assertIn("TEAMS_WEBHOOK_URL", str(context.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
