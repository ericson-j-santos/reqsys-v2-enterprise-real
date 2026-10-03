"""Testes de caminhos críticos — Actions Runtime Center API."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.actions_runtime_monitor import WorkflowRunSnapshot, classificar_runs, decidir_estado

client = TestClient(app)


def _admin_headers():
    login = client.post(
        "/v1/auth/login",
        json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"},
    )
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_status_actions_runtime_requer_autenticacao():
    res = client.get("/v1/actions-runtime/status")
    assert res.status_code == 401


def test_status_actions_runtime_expoe_capacidades():
    res = client.get("/v1/actions-runtime/status", headers=_admin_headers())

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["servico"] == "actions-runtime-center"
    assert "pareto_falhas" in data["capacidades"]


def test_snapshot_manual_classifica_runs():
    res = client.post(
        "/v1/actions-runtime/snapshot",
        headers=_admin_headers(),
        json={
            "runs": [
                {"id": 1, "name": "CI", "status": "completed", "conclusion": "success"},
                {"id": 2, "name": "Deploy", "status": "completed", "conclusion": "failure"},
            ]
        },
    )

    assert res.status_code == 200
    snapshot = res.json()["data"]
    assert snapshot["decisao"] == "corrigir_falhas_de_actions_antes_de_novo_merge"
    assert snapshot["pareto_falhas"]["total_causes"] == 1


def test_github_runs_propaga_erro_de_api():
    with patch(
        "app.api.actions_runtime_center.GitHubActionsClient.listar_runs",
        side_effect=RuntimeError("token ausente"),
    ):
        res = client.get("/v1/actions-runtime/github/runs", headers=_admin_headers())

    assert res.status_code == 502


def test_github_webhook_evento_nao_workflow_run():
    res = client.post(
        "/v1/actions-runtime/webhook/github",
        headers=_admin_headers(),
        json={"action": "ping"},
    )

    assert res.status_code == 200
    body = res.json()["data"]
    assert body["processado"] is False
    assert body["tipo"] == "evento_nao_workflow_run"


def test_github_webhook_processa_workflow_run():
    res = client.post(
        "/v1/actions-runtime/webhook/github",
        headers=_admin_headers(),
        json={
            "workflow_run": {
                "id": 99,
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
            }
        },
    )

    assert res.status_code == 200
    body = res.json()["data"]
    assert body["processado"] is True
    assert body["run"]["health"] == "unhealthy"
    assert body["decisao"] == "corrigir_falhas_de_actions_antes_de_novo_merge"


def test_github_runs_lista_com_token_mockado():
    from app.services.actions_runtime_monitor import WorkflowRunSnapshot

    runs_mock = [
        WorkflowRunSnapshot(
            run_id=10,
            workflow="CI",
            status="completed",
            conclusion="success",
            branch="main",
            event="push",
            commit_sha="sha",
            html_url="https://example.com/10",
            created_at=None,
            updated_at=None,
        )
    ]
    with patch(
        "app.api.actions_runtime_center.GitHubActionsClient.listar_runs",
        return_value=runs_mock,
    ):
        res = client.get("/v1/actions-runtime/github/runs", headers=_admin_headers())

    assert res.status_code == 200
    body = res.json()["data"]
    assert body["runs"][0]["health"] == "healthy"
    assert body["resumo"]["decisao"] == "operacao_estavel"


def test_decidir_estado_operacao_estavel_e_instabilidade():
    sucesso = WorkflowRunSnapshot(
        run_id=1,
        workflow="CI",
        status="completed",
        conclusion="success",
        branch="main",
        event="push",
        commit_sha="abc",
        html_url=None,
        created_at=None,
        updated_at=None,
    )
    assert decidir_estado(96.0, [], []) == "operacao_estavel"
    assert classificar_runs([sucesso])["decisao"] == "operacao_estavel"

    desconhecido = WorkflowRunSnapshot(
        run_id=2,
        workflow="Nightly",
        status="completed",
        conclusion="neutral",
        branch="main",
        event="schedule",
        commit_sha="def",
        html_url=None,
        created_at=None,
        updated_at=None,
    )
    assert classificar_runs([sucesso, desconhecido])["decisao"] == "investigar_instabilidade_operacional"
