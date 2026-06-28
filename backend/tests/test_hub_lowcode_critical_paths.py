"""Testes de caminhos críticos — Hub Low-Code API e tracker IA."""

from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini import _UsageTracker

client = TestClient(app)


def test_usage_tracker_snapshot_reseta_leitura_em_novo_dia():
    tracker = _UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker._dia_atual = date(2020, 1, 1)
    tracker._total_dia = 8

    snapshot = tracker.snapshot()

    assert snapshot["req_hoje"] == 0
    assert snapshot["restante_dia"] == 10
    assert snapshot["pct_dia_usado"] == 0.0


def test_usage_tracker_registra_requisicoes():
    tracker = _UsageTracker(limite_por_minuto=5, limite_por_dia=10)
    tracker.registrar()
    tracker.registrar()

    snapshot = tracker.snapshot()
    assert snapshot["req_hoje"] == 2
    assert snapshot["req_ultimo_minuto"] == 2


def test_hub_lowcode_status_endpoint():
    with patch("app.api.hub_lowcode.status_consolidado", AsyncMock(return_value={"ambientes": 1})):
        res = client.get("/v1/hub-lowcode/status")

    assert res.status_code == 200
    assert res.json()["data"]["ambientes"] == 1


def test_hub_lowcode_endpoints_de_listagem():
    patches = {
        "/v1/hub-lowcode/pacotes": ("listar_pacotes_ia", [{"nome": "pkg"}]),
        "/v1/hub-lowcode/flows": ("listar_flows_pa", [{"nome": "flow"}]),
        "/v1/hub-lowcode/github": ("listar_runs_github", [{"id": 1}]),
        "/v1/hub-lowcode/powerplatform/ambientes": ("listar_ambientes_powerplatform", [{"id": "env"}]),
        "/v1/hub-lowcode/planner/descobrir?group_id=grp-1": (
            "descobrir_planos_planner",
            [{"id": "plan"}],
        ),
    }
    for path, (func_name, payload) in patches.items():
        with patch(f"app.api.hub_lowcode.{func_name}", AsyncMock(return_value=payload)):
            res = client.get(path)
        assert res.status_code == 200
        assert res.json()["success"] is True


def test_hub_lowcode_planner_webhook_config_e_historico():
    with patch(
        "app.api.hub_lowcode.obter_planner_webhook_config",
        return_value={"configurado": True, "teams_configurado": False, "webhook_url": "https://example.com/hook"},
    ):
        res = client.get("/v1/hub-lowcode/planner/webhook-config")

    assert res.status_code == 200
    assert res.json()["data"]["configurado"] is True

    with patch(
        "app.api.hub_lowcode.salvar_planner_webhook_config",
        return_value={"salvo": True},
    ):
        res = client.put(
            "/v1/hub-lowcode/planner/webhook-config",
            json={"webhook_url": "https://example.com/hook"},
        )

    assert res.status_code == 200
    assert res.json()["data"]["salvo"] is True

    with patch("app.api.hub_lowcode.listar_historico_integracoes", return_value=[{"tipo": "planner"}]):
        res = client.get("/v1/hub-lowcode/integracoes/historico?tipo=planner")

    assert res.status_code == 200
    assert res.json()["data"][0]["tipo"] == "planner"


def test_hub_lowcode_publicar_tarefas_e_testar_teams():
    with patch(
        "app.api.hub_lowcode.publicar_tarefas_planner",
        AsyncMock(return_value={"ok": True, "criadas": 2}),
    ):
        res = client.post(
            "/v1/hub-lowcode/planner/tasks",
            json={"tarefas_texto": "Tarefa|Dev|2026-06-28|Backlog|Alta|Desc"},
        )

    assert res.status_code == 200
    assert res.json()["data"]["criadas"] == 2

    with patch("app.api.hub_lowcode.testar_teams_webhook", AsyncMock(return_value={"enviado": True})):
        res = client.post(
            "/v1/hub-lowcode/teams/testar-webhook",
            json="https://teams.example.com/webhook",
        )

    assert res.status_code == 200
    assert res.json()["data"]["enviado"] is True
