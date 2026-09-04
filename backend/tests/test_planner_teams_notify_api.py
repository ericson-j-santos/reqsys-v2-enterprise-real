from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.planner_teams_notify import require_planner_teams_auth
from app.core.config import settings
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _payload(**overrides):
    data = {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'planner_connection_id': 'planner-connection-dev',
        'target_environment': 'dev',
        'confirmar': False,
    }
    data.update(overrides)
    return data


def _auth_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture
def planner_teams_auth_override():
    app.dependency_overrides[require_planner_teams_auth] = _auth_ctx
    yield
    app.dependency_overrides.pop(require_planner_teams_auth, None)


def test_contract_expoe_eventos_e_perfil(planner_teams_auth_override):
    response = client.get('/v1/hub-lowcode/planner-teams-notify/contract')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['profile'] == 'planner_teams_notificacao_simples'
    assert data['eventos'] == ['concluida', 'criada']
    assert data['writes_back_to_planner'] is False


def test_validate_happy_path(planner_teams_auth_override, monkeypatch):
    monkeypatch.setattr(settings, 'teams_notifications_webhook_url', 'https://tieri.webhook.office.com/webhookb2/fake')
    with patch('app.api.planner_teams_notify.validar_destino_assistente', new=AsyncMock(return_value={'id': 'env-dev'})):
        response = client.post('/v1/hub-lowcode/planner-teams-notify/validate', json=_payload())

    assert response.status_code == 200
    bundle = response.json()['data']
    assert bundle['profile'] == 'planner_teams_notificacao_simples'
    assert len(bundle['flows']) == 2


def test_validate_propaga_erro_de_destino_como_409(planner_teams_auth_override):
    with patch(
        'app.api.planner_teams_notify.validar_destino_assistente',
        new=AsyncMock(side_effect=ValueError('producao bloqueada')),
    ):
        response = client.post('/v1/hub-lowcode/planner-teams-notify/validate', json=_payload())

    assert response.status_code == 409


def test_deploy_happy_path_envia_webhook_do_backend(planner_teams_auth_override, monkeypatch):
    monkeypatch.setattr(settings, 'teams_notifications_webhook_url', 'https://tieri.webhook.office.com/webhookb2/fake')
    with patch('app.api.planner_teams_notify.validar_destino_assistente', new=AsyncMock(return_value={'id': 'env-dev'})), \
         patch('app.api.planner_teams_notify.despachar', new=AsyncMock(return_value={'dispatched': True, 'correlation_id': 'cid-1'})) as despachar_mock:
        response = client.post(
            '/v1/hub-lowcode/planner-teams-notify/deploy',
            json=_payload(confirmar=True),
            headers={'X-Power-Automate-Token': 'flow-token-123'},
        )

    assert response.status_code == 200
    assert response.json()['data']['dispatched'] is True
    chamada_payload, chamada_kwargs = despachar_mock.call_args
    assert chamada_payload[0]['teams_webhook_url']
    assert chamada_kwargs['user_token'] == 'flow-token-123'


def test_deploy_propaga_erro_de_destino_como_409(planner_teams_auth_override):
    with patch(
        'app.api.planner_teams_notify.validar_destino_assistente',
        new=AsyncMock(side_effect=ValueError('producao bloqueada')),
    ):
        response = client.post('/v1/hub-lowcode/planner-teams-notify/deploy', json=_payload(confirmar=True))

    assert response.status_code == 409
