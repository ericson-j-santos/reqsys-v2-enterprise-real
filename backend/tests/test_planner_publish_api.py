"""Testes de API — rotas governadas de publicação no Planner (issue #32)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.hub_lowcode import require_planner_publish_auth
from app.core.security import get_current_user
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


def _fake_user():
    return {'sub': 'admin@teste', 'papel': 'admin'}


@pytest.fixture
def auth_override():
    app.dependency_overrides[require_planner_publish_auth] = _fake_ctx
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(require_planner_publish_auth, None)
    app.dependency_overrides.pop(get_current_user, None)


def _payload(**overrides):
    base = {
        'planId': 'plan-1',
        'bucketId': 'bucket-1',
        'title': 'Revisar contrato Planner',
        'description': 'Descricao',
        'dueDate': '2026-09-01',
        'priority': 'alta',
        'sourceId': 'requisito:1234',
        'requester': 'tester@example.com',
    }
    base.update(overrides)
    return base


def test_publish_sem_auth_retorna_401_ou_403():
    response = client.post('/v1/hub-lowcode/planner/publish', json=_payload())
    assert response.status_code in (401, 403)


@patch('app.api.hub_lowcode.publicar_tarefa_planner_governada', new_callable=AsyncMock)
def test_publish_happy_path(mock_publicar, auth_override):
    mock_publicar.return_value = {
        'ok': True, 'status': 'publicado', 'idempotency_key': 'abc123',
        'attempt_id': 1, 'correlation_id': 'corr-1', 'planner_task_id': 'task-1', 'erro': None,
    }
    response = client.post('/v1/hub-lowcode/planner/publish', json=_payload())
    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'publicado'
    assert data['attempt_id'] == 1


def test_publish_campo_obrigatorio_faltando_retorna_422(auth_override):
    payload = _payload()
    del payload['sourceId']
    response = client.post('/v1/hub-lowcode/planner/publish', json=payload)
    assert response.status_code == 422


@patch('app.api.hub_lowcode.obter_status_tentativa_planner_publish')
def test_publish_status_nao_encontrado_retorna_404(mock_status, auth_override):
    mock_status.return_value = None
    response = client.get('/v1/hub-lowcode/planner/publish/999999')
    assert response.status_code == 404


@patch('app.api.hub_lowcode.obter_status_tentativa_planner_publish')
def test_publish_status_encontrado(mock_status, auth_override):
    mock_status.return_value = {
        'ok': True, 'status': 'publicado', 'idempotency_key': 'abc123',
        'attempt_id': 5, 'correlation_id': 'corr-5', 'planner_task_id': 'task-5', 'erro': None,
    }
    response = client.get('/v1/hub-lowcode/planner/publish/5')
    assert response.status_code == 200
    assert response.json()['data']['attempt_id'] == 5


@patch('app.api.hub_lowcode.listar_tentativas_planner_publish')
def test_publish_listar(mock_listar, auth_override):
    mock_listar.return_value = [
        {'ok': True, 'status': 'publicado', 'idempotency_key': 'a', 'attempt_id': 1,
         'correlation_id': 'c1', 'planner_task_id': 't1', 'erro': None},
    ]
    response = client.get('/v1/hub-lowcode/planner/publish?source_id=requisito:1234')
    assert response.status_code == 200
    assert len(response.json()['data']['items']) == 1


def test_publish_listar_sem_auth_retorna_401():
    response = client.get('/v1/hub-lowcode/planner/publish')
    assert response.status_code == 401


@patch('app.api.hub_lowcode.listar_tentativas_planner_publish')
def test_publish_listar_usuario_nao_admin_le_normalmente(mock_listar):
    """Leitura (issue #32 status screen) deve funcionar para qualquer usuário
    logado — não só admin — já que o Painel de Integrações é acessível a todos
    os papéis com `dashboard:read`. Só publicar/reprocessar exige admin."""
    app.dependency_overrides[get_current_user] = lambda: {'sub': 'analista@teste', 'papel': 'analista'}
    try:
        mock_listar.return_value = []
        response = client.get('/v1/hub-lowcode/planner/publish')
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_publish_reprocessar_sem_auth_retorna_401_ou_403():
    """Reprocessar continua exigindo admin/service-token mesmo com o relax da
    leitura acima — é uma ação de escrita (reenvio ao Planner)."""
    response = client.post('/v1/hub-lowcode/planner/publish/1/reprocessar')
    assert response.status_code in (401, 403)


@patch('app.api.hub_lowcode.reprocessar_tentativa_planner_publish', new_callable=AsyncMock)
def test_publish_reprocessar_tentativa_ja_publicada_retorna_409(mock_reprocessar, auth_override):
    mock_reprocessar.side_effect = ValueError('Tentativa 1 já está "publicado" — reprocessamento recusado')
    response = client.post('/v1/hub-lowcode/planner/publish/1/reprocessar')
    assert response.status_code == 409


@patch('app.api.hub_lowcode.reprocessar_tentativa_planner_publish', new_callable=AsyncMock)
def test_publish_reprocessar_sucesso(mock_reprocessar, auth_override):
    mock_reprocessar.return_value = {
        'ok': True, 'status': 'publicado', 'idempotency_key': 'abc123',
        'attempt_id': 2, 'correlation_id': 'corr-2', 'planner_task_id': 'task-2', 'erro': None,
    }
    response = client.post('/v1/hub-lowcode/planner/publish/2/reprocessar')
    assert response.status_code == 200
    assert response.json()['data']['status'] == 'publicado'
