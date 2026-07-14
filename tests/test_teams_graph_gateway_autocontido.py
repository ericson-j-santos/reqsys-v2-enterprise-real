from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "geradores" / "teams_graph_gateway_autocontido.py"
spec = spec_from_file_location("teams_graph_gateway_autocontido", MODULE_PATH)
assert spec and spec.loader
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_safe_json_aceita_resposta_textual_do_teams():
    assert module.HttpClient.safe_json("1") == {"value": 1}
    assert module.HttpClient.safe_json("Accepted") == {"message": "Accepted"}
    assert module.HttpClient.safe_json("") == {}


def test_webhook_dry_run_gera_evidencia_sem_rede():
    config = module.GatewayConfig(webhook_url="https://example.invalid/hook")
    result = module.TeamsGateway(config).send_webhook("commit abc123", "ReqSys", dry_run=True)

    assert result.success is True
    assert result.route == "webhook"
    assert result.correlation_id
    assert result.response["planned"] is True


def test_webhook_exige_configuracao():
    gateway = module.TeamsGateway(module.GatewayConfig())

    try:
        gateway.send_webhook("mensagem", "ReqSys")
    except module.GatewayError as exc:
        assert "TEAMS_WEBHOOK_URL" in str(exc)
    else:
        raise AssertionError("Gateway deveria rejeitar webhook não configurado")
