from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_admin
from app.main import app


def _fake_admin():
    return {'sub': 'operational-deploy-retirement-test', 'papel': 'admin'}


@pytest.fixture(autouse=True)
def _admin_override():
    app.dependency_overrides[require_admin] = _fake_admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_catalogo_informa_retirada_definitiva():
    response = TestClient(app).get('/v1/actions-runtime/operational-deploy/catalog')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'RETIRADO'
    assert data['habilitado'] is False
    assert data['production_touched'] is False
    assert data['aplicacoes'] == []
    assert 'não despacha mais workflows' in data['motivo']


def test_validacao_retorna_410_sem_despachar_workflow():
    with patch('requests.post') as post:
        response = TestClient(app).post(
            '/v1/actions-runtime/operational-deploy/validate',
            json={'aplicacao': 'backend'},
        )

    assert response.status_code == 410
    assert 'retirada' in response.json()['detail'].lower()
    post.assert_not_called()


def test_execucao_confirmada_retorna_410_sem_despachar_workflow():
    with patch('requests.post') as post:
        response = TestClient(app).post(
            '/v1/actions-runtime/operational-deploy/execute',
            json={'aplicacao': 'backend', 'confirmar': True},
        )

    assert response.status_code == 410
    assert response.json()['detail'] == 'Implantação operacional retirada: o ReqSys não despacha mais workflows de deploy no Fly.io.'
    post.assert_not_called()
