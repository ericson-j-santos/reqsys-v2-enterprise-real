from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.operational_orchestrator import OperationalOrchestrator, OperationalStore


client = TestClient(app)


def _admin_headers() -> dict[str, str]:
    login = client.post(
        "/v1/auth/login",
        json={"email": "ericsonjosedossantos@tieri659.onmicrosoft.com"},
    )
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_orchestrator(tmp_path: Path, *, configured: bool = True) -> OperationalOrchestrator:
    manifest = tmp_path / "readiness.yaml"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "environment": "development-api-test",
                "capabilities": {
                    "excel": {
                        "required": True,
                        "source": "env",
                        "references": ["REQSYS_API_TEST_EXCEL"],
                        "description": "Excel controlado pelo teste",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    environ = {"REQSYS_API_TEST_EXCEL": "configured"} if configured else {}
    return OperationalOrchestrator(
        store=OperationalStore(tmp_path / "state.sqlite3"),
        manifest_path=manifest,
        environ=environ,
    )


def test_orchestrator_cycle_api_persiste_evidencia(tmp_path: Path, monkeypatch):
    orchestrator = _build_orchestrator(tmp_path)
    monkeypatch.setattr(
        "app.api.actions_runtime_center._operational_orchestrator",
        lambda: orchestrator,
    )

    response = client.post(
        "/v1/actions-runtime/orchestrator/cycle",
        headers=_admin_headers(),
        json={"sha": "sha-api-current", "branch": "feature/api"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["execution"]["result"]["status"] == "ready"
    correlation_id = data["execution"]["action"]["correlation_id"]

    evidence = client.get(
        "/v1/actions-runtime/orchestrator/evidence",
        headers=_admin_headers(),
        params={"correlation_id": correlation_id},
    )
    assert evidence.status_code == 200
    items = evidence.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["sha"] == "sha-api-current"


def test_orchestrator_readiness_api_bloqueia_sem_referencia(tmp_path: Path, monkeypatch):
    orchestrator = _build_orchestrator(tmp_path, configured=False)
    monkeypatch.setattr(
        "app.api.actions_runtime_center._operational_orchestrator",
        lambda: orchestrator,
    )

    response = client.get(
        "/v1/actions-runtime/orchestrator/readiness",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "blocked"
    assert data["missing_required"] == ["excel"]


def test_orchestrator_ingest_ci_failure_cria_acao_amarela(tmp_path: Path, monkeypatch):
    orchestrator = _build_orchestrator(tmp_path)
    monkeypatch.setattr(
        "app.api.actions_runtime_center._operational_orchestrator",
        lambda: orchestrator,
    )

    response = client.post(
        "/v1/actions-runtime/orchestrator/ingest/workflow-run",
        headers=_admin_headers(),
        json={
            "workflow_run": {
                "id": 501,
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "feature/failure",
                "head_sha": "sha-failure-current",
            }
        },
    )

    assert response.status_code == 200
    action = response.json()["data"]["action"]
    assert action["risk"] == "yellow"
    assert action["status"] == "awaiting_approval"
    assert action["executor"] == "github_agent"


def test_orchestrator_status_actions_e_execute_api(tmp_path: Path, monkeypatch):
    orchestrator = _build_orchestrator(tmp_path)
    monkeypatch.setattr(
        "app.api.actions_runtime_center._operational_orchestrator",
        lambda: orchestrator,
    )
    headers = _admin_headers()

    status_response = client.get(
        "/v1/actions-runtime/orchestrator/status",
        headers=headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["service"] == "reqsys-operational-orchestrator"

    action, created = orchestrator.enqueue_readiness_check(
        sha="sha-api-execute",
        branch="feature/api-execute",
    )
    assert created is True

    actions_response = client.get(
        "/v1/actions-runtime/orchestrator/actions",
        headers=headers,
        params={"status": "ready"},
    )
    assert actions_response.status_code == 200
    assert actions_response.json()["data"]["total"] == 1

    execute_response = client.post(
        f"/v1/actions-runtime/orchestrator/actions/{action.action_id}/execute",
        headers=headers,
        json={"confirmar": False},
    )
    assert execute_response.status_code == 200
    assert execute_response.json()["data"]["action"]["status"] == "succeeded"

    missing_response = client.post(
        "/v1/actions-runtime/orchestrator/actions/ACT-INEXISTENTE/execute",
        headers=headers,
        json={"confirmar": True},
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Ação não encontrada."


def test_orchestrator_endpoints_falham_fechado_sem_manifesto(tmp_path: Path, monkeypatch):
    orchestrator = OperationalOrchestrator(
        store=OperationalStore(tmp_path / "state.sqlite3"),
        manifest_path=tmp_path / "missing-readiness.yaml",
        environ={},
    )
    monkeypatch.setattr(
        "app.api.actions_runtime_center._operational_orchestrator",
        lambda: orchestrator,
    )
    headers = _admin_headers()

    status_response = client.get(
        "/v1/actions-runtime/orchestrator/status",
        headers=headers,
    )
    readiness_response = client.get(
        "/v1/actions-runtime/orchestrator/readiness",
        headers=headers,
    )
    cycle_response = client.post(
        "/v1/actions-runtime/orchestrator/cycle",
        headers=headers,
        json={"sha": "sha-missing-manifest", "branch": "feature/api"},
    )

    assert status_response.status_code == 422
    assert readiness_response.status_code == 422
    assert cycle_response.status_code == 422
    assert "Manifesto de readiness ausente" in status_response.json()["detail"]
