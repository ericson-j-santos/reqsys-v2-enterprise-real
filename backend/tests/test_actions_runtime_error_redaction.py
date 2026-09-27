"""Regressao: Actions Runtime Center nao pode vazar detalhes internos em respostas HTTP."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app
from app.services.operational_orchestrator import ManifestError, OperationalOrchestratorError

client = TestClient(app)

_INTERNAL_MARKER = "internal-token=super-secret-value"


def _fake_admin():
    return {"sub": "security-regression-test", "papel": "admin"}


@pytest.fixture(autouse=True)
def _admin_override():
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


def _assert_redacted(response, *, status_code: int, detail: str) -> None:
    assert response.status_code == status_code
    assert response.json()["detail"] == detail
    assert _INTERNAL_MARKER not in response.text


def test_github_runs_internal_error_is_redacted():
    with patch(
        "app.api.actions_runtime_center.GitHubActionsClient.listar_runs",
        side_effect=RuntimeError(_INTERNAL_MARKER),
    ):
        response = client.get("/v1/actions-runtime/github/runs")

    _assert_redacted(
        response,
        status_code=502,
        detail="Falha ao consultar GitHub Actions.",
    )


def test_deploy_validation_value_error_is_redacted():
    with patch(
        "app.api.actions_runtime_center.preparar_deploy_dev",
        side_effect=ValueError(_INTERNAL_MARKER),
    ):
        response = client.post(
            "/v1/actions-runtime/operational-deploy/validate",
            json={"aplicacao": "backend"},
        )

    _assert_redacted(
        response,
        status_code=422,
        detail="Solicitacao de deploy DEV invalida.",
    )


def test_deploy_execution_value_error_is_redacted():
    with patch(
        "app.api.actions_runtime_center.executar_deploy_dev",
        side_effect=ValueError(_INTERNAL_MARKER),
    ):
        response = client.post(
            "/v1/actions-runtime/operational-deploy/execute",
            json={"aplicacao": "backend", "confirmar": True},
        )

    _assert_redacted(
        response,
        status_code=422,
        detail="Solicitacao de deploy DEV invalida.",
    )


def test_deploy_execution_unexpected_error_is_redacted():
    with patch(
        "app.api.actions_runtime_center.executar_deploy_dev",
        side_effect=RuntimeError(_INTERNAL_MARKER),
    ):
        response = client.post(
            "/v1/actions-runtime/operational-deploy/execute",
            json={"aplicacao": "backend", "confirmar": True},
        )

    _assert_redacted(
        response,
        status_code=502,
        detail="Falha ao acionar execucao governada.",
    )


def test_orchestrator_status_error_is_redacted():
    orchestrator = MagicMock()
    orchestrator.status.side_effect = ManifestError(_INTERNAL_MARKER)
    with patch("app.api.actions_runtime_center._operational_orchestrator", return_value=orchestrator):
        response = client.get("/v1/actions-runtime/orchestrator/status")

    _assert_redacted(
        response,
        status_code=422,
        detail="Estado do orquestrador invalido ou indisponivel.",
    )


def test_orchestrator_readiness_error_is_redacted():
    orchestrator = MagicMock()
    orchestrator.readiness.side_effect = ManifestError(_INTERNAL_MARKER)
    with patch("app.api.actions_runtime_center._operational_orchestrator", return_value=orchestrator):
        response = client.get("/v1/actions-runtime/orchestrator/readiness")

    _assert_redacted(
        response,
        status_code=422,
        detail="Readiness do orquestrador invalido ou indisponivel.",
    )


def test_orchestrator_cycle_error_is_redacted():
    orchestrator = MagicMock()
    orchestrator.run_cycle.side_effect = OperationalOrchestratorError(_INTERNAL_MARKER)
    with patch("app.api.actions_runtime_center._operational_orchestrator", return_value=orchestrator):
        response = client.post(
            "/v1/actions-runtime/orchestrator/cycle",
            json={"sha": "sha-security-test", "branch": "feature/security"},
        )

    _assert_redacted(
        response,
        status_code=422,
        detail="Ciclo operacional invalido.",
    )


def test_orchestrator_execute_error_is_redacted():
    orchestrator = MagicMock()
    orchestrator.execute.side_effect = OperationalOrchestratorError(_INTERNAL_MARKER)
    with patch("app.api.actions_runtime_center._operational_orchestrator", return_value=orchestrator):
        response = client.post(
            "/v1/actions-runtime/orchestrator/actions/ACT-SECURITY/execute",
            json={"confirmar": True},
        )

    _assert_redacted(
        response,
        status_code=422,
        detail="Execucao da acao operacional invalida.",
    )


def test_orchestrator_ingest_error_is_redacted():
    orchestrator = MagicMock()
    orchestrator.ingest_workflow_run.side_effect = OperationalOrchestratorError(_INTERNAL_MARKER)
    with patch("app.api.actions_runtime_center._operational_orchestrator", return_value=orchestrator):
        response = client.post(
            "/v1/actions-runtime/orchestrator/ingest/workflow-run",
            json={
                "workflow_run": {
                    "id": 501,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "failure",
                }
            },
        )

    _assert_redacted(
        response,
        status_code=422,
        detail="Workflow run invalido para ingestao.",
    )
