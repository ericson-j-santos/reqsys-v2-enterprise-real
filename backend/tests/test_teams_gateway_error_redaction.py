"""Regressao: erros internos do Teams Gateway nao podem vazar para respostas HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.teams_gateway import require_promover_solution_auth
from app.core.security import require_admin
from app.core.service_tokens import ServiceAuthContext
from app.db import get_db
from app.main import app

client = TestClient(app)

_INTERNAL_MARKER = "internal-token=super-secret-value"


def _fake_admin():
    return {"papel": "admin"}


def _fake_promote_context():
    return ServiceAuthContext(ator="security-regression-test", via_token=False)


@pytest.fixture(autouse=True)
def _safe_dependencies():
    def override_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = _fake_admin
    app.dependency_overrides[require_promover_solution_auth] = _fake_promote_context
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(require_promover_solution_auth, None)


@pytest.mark.parametrize(
    ("target", "method", "url", "payload", "expected_detail"),
    [
        (
            "app.api.teams_gateway.atualizar_destinatario",
            "PATCH",
            "/v1/teams-gateway/recipient-policies/recipients/999",
            {"ativo": True},
            "Destinatario Teams nao encontrado.",
        ),
        (
            "app.api.teams_gateway.remover_destinatario",
            "DELETE",
            "/v1/teams-gateway/recipient-policies/recipients/999",
            None,
            "Destinatario Teams nao encontrado.",
        ),
        (
            "app.api.teams_gateway.atualizar_flow_bot_owner",
            "PATCH",
            "/v1/teams-gateway/flow-bot/owners/999",
            {"ativo": True},
            "Dono do flow_bot nao encontrado.",
        ),
        (
            "app.api.teams_gateway.remover_flow_bot_owner",
            "DELETE",
            "/v1/teams-gateway/flow-bot/owners/999",
            None,
            "Dono do flow_bot nao encontrado.",
        ),
    ],
)
def test_crud_domain_errors_are_redacted(target, method, url, payload, expected_detail):
    kwargs = {"json": payload} if payload is not None else {}
    with patch(target, side_effect=ValueError(_INTERNAL_MARKER)):
        response = client.request(method, url, **kwargs)

    assert response.status_code == 404
    assert response.json()["detail"] == expected_detail
    assert _INTERNAL_MARKER not in response.text


@patch("app.api.teams_gateway.listar_workflows_da_solution", new_callable=AsyncMock)
def test_solution_lookup_value_error_is_redacted(mock_listar):
    mock_listar.side_effect = ValueError(_INTERNAL_MARKER)

    response = client.get(
        "/v1/teams-gateway/flow-bot/solutions/ReqSysTeamsGateway/flows",
        params={"environment": "https://org.crm2.dynamics.com"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Solution nao encontrada ou invalida."
    assert _INTERNAL_MARKER not in response.text


@patch("app.api.teams_gateway.clonar_flow_para_novo_dono", new_callable=AsyncMock)
def test_clone_value_error_is_redacted(mock_clonar):
    mock_clonar.side_effect = ValueError(_INTERNAL_MARKER)

    response = client.post(
        "/v1/teams-gateway/flow-bot/clonar-flow",
        json={
            "environment": "env-1",
            "flow_id_origem": "flow-origem",
            "nova_connection_id": "conn-backup",
            "novo_display_name": "Backup 1",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Solicitacao de clonagem do flow invalida."
    assert _INTERNAL_MARKER not in response.text


@patch("app.api.teams_gateway.promover_flow_para_ambiente", new_callable=AsyncMock)
def test_promotion_value_error_is_redacted(mock_promover):
    mock_promover.side_effect = ValueError(_INTERNAL_MARKER)

    response = client.post(
        "/v1/teams-gateway/flow-bot/promover-solution",
        json={
            "environment_url_origem": "https://org-dev.crm2.dynamics.com",
            "environment_url_destino": "https://org-prod.crm2.dynamics.com",
            "solution_name": "ReqSysTeamsGateway",
            "connection_reference_logical_name": "reqsys_teams_ref",
            "connection_id_destino": "conn-prod-dono",
            "novo_flow_display_name": "ReqSys Flow Bot - Prod",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Solicitacao de promocao da Solution invalida."
    assert _INTERNAL_MARKER not in response.text
