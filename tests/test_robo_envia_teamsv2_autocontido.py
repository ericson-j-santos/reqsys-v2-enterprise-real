import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_NAME = "robo_envia_teamsv2_autocontido"
MODULE_PATH = Path(__file__).parents[1] / "tools" / "geradores" / "robo_envia_teamsv2_autocontido.py"
spec = spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert spec and spec.loader
module = module_from_spec(spec)
sys.modules[MODULE_NAME] = module
spec.loader.exec_module(module)


class FakeHttpClient:
    """Substitui o HttpClient real -- permite validar envio (URL/payload) sem rede."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def post(self, url, payload):
        self.chamadas.append((url, payload))
        return self.respostas.pop(0)


def payload_valido(**overrides):
    base = {
        "to": "fulano@tieri659.onmicrosoft.com",
        "title": "Aviso",
        "content": "corpo",
        "signature": "ReqSys",
    }
    base.update(overrides)
    return base


class LogicaDoFlowTest(unittest.TestCase):
    """Fidelidade das funções puras -- v2 herda a mesma validação da v1 (clone)."""

    def test_condicao_replica_a_expressao_real_do_if(self):
        self.assertTrue(module.condicao(payload_valido()))
        self.assertFalse(module.condicao(payload_valido(to="sem-arroba")))
        self.assertFalse(module.condicao(payload_valido(content="")))
        self.assertFalse(module.condicao(payload_valido(title="")))

    def test_correlation_id_final_prioriza_o_recebido_no_payload(self):
        self.assertEqual(module.compose_correlation_id_final({"correlationId": "abc"}, "gerado"), "abc")
        self.assertEqual(module.compose_correlation_id_final({}, "gerado"), "gerado")

    def test_montar_payload_trigger_normaliza_to_e_nao_inclui_envelope_de_card(self):
        payload = module.montar_payload_trigger(
            payload_valido(to=" Fulano@Tieri659.OnMicrosoft.com "), "2026-08-04T10:00:00-03:00", "corr-1"
        )
        self.assertEqual(payload["to"], "fulano@tieri659.onmicrosoft.com")
        self.assertEqual(payload["correlationId"], "corr-1")
        self.assertNotIn("poster", payload)
        self.assertNotIn("messageBody", payload)


class EnvioTest(unittest.TestCase):
    """Testes de envio: exercitam o caminho real de disparo (com transporte HTTP fake)."""

    def test_dry_run_nunca_finge_sucesso_real(self):
        fluxo = module.RoboEnviaTeamsV2(module.FluxoConfig())
        resultado = fluxo.executar(payload_valido(), dry_run=True)

        self.assertFalse(resultado.enviado)
        self.assertTrue(resultado.body.get("planned"))
        self.assertNotIn("ok", resultado.body)

    def test_payload_invalido_retorna_400_sem_enviar(self):
        fluxo = module.RoboEnviaTeamsV2(module.FluxoConfig())
        resultado = fluxo.executar(payload_valido(to="sem-arroba"), dry_run=False)

        self.assertEqual(resultado.status_code, 400)
        self.assertFalse(resultado.enviado)
        self.assertFalse(resultado.body["ok"])

    def test_campo_obrigatorio_ausente_cai_no_scope_catch(self):
        fluxo = module.RoboEnviaTeamsV2(module.FluxoConfig())
        resultado = fluxo.executar({"to": "fulano@x.com", "title": "T"}, dry_run=False)

        self.assertEqual(resultado.status_code, 500)
        self.assertFalse(resultado.enviado)
        self.assertEqual(resultado.body["error"], "Falha interna no envio")

    def test_envio_real_sem_trigger_url_nunca_finge_sucesso(self):
        fluxo = module.RoboEnviaTeamsV2(module.FluxoConfig(trigger_url=None))
        resultado = fluxo.executar(payload_valido(), dry_run=False)

        self.assertEqual(resultado.status_code, 500)
        self.assertFalse(resultado.enviado)
        self.assertIn("TEAMS_FLOW_BOT_V2_TRIGGER_URL", resultado.body["detalhe"])

    def test_envio_real_chama_http_com_url_e_payload_corretos(self):
        fake_http = FakeHttpClient([(200, {"ok": True})])
        config = module.FluxoConfig(trigger_url="https://flow.example.invalid/invoke")
        fluxo = module.RoboEnviaTeamsV2(config, http=fake_http)

        resultado = fluxo.executar(payload_valido(to="Fulano@Tieri659.OnMicrosoft.com"), dry_run=False)

        self.assertEqual(resultado.status_code, 200)
        self.assertTrue(resultado.enviado)
        self.assertTrue(resultado.body["ok"])
        self.assertEqual(len(fake_http.chamadas), 1)
        url_chamada, payload_enviado = fake_http.chamadas[0]
        self.assertEqual(url_chamada, "https://flow.example.invalid/invoke")
        self.assertEqual(payload_enviado["to"], "fulano@tieri659.onmicrosoft.com")
        self.assertNotIn("poster", payload_enviado)

    def test_erro_http_do_flow_nao_vira_sucesso_fingido(self):
        fake_http = FakeHttpClient([(500, {"error": "boom"})])
        config = module.FluxoConfig(trigger_url="https://flow.example.invalid/invoke")
        fluxo = module.RoboEnviaTeamsV2(config, http=fake_http)

        resultado = fluxo.executar(payload_valido(), dry_run=False)

        self.assertEqual(resultado.status_code, 500)
        self.assertFalse(resultado.enviado)
        self.assertFalse(resultado.body["ok"])

    def test_self_test_do_modulo_passa(self):
        resultado = module.self_test()
        self.assertEqual(resultado["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
