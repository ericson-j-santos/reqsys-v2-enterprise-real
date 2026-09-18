"""Testes de caminhos críticos — API sistema (endpoints e health-check)."""

import os
from unittest.mock import MagicMock

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_sistema_api.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.db import get_db
from app.main import app


def test_listar_endpoints_retorna_catalogo(client):
    response = client.get('/v1/sistema/endpoints')
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    data = body['data']
    assert data['total_endpoints'] >= 1
    assert isinstance(data['endpoints'], list)
    primeiro = data['endpoints'][0]
    assert {'id', 'metodo', 'url', 'descricao', 'autenticacao_requerida'} <= set(primeiro.keys())


def test_health_check_reporta_erro_de_database(client):
    mock_db = MagicMock()
    mock_db.query.side_effect = RuntimeError('database offline')

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/v1/sistema/health-check')
        assert response.status_code == 200
        componentes = response.json()['data']['componentes']
        assert componentes['database']['status'] == 'erro'
        assert 'database offline' in componentes['database']['detalhe']
        assert response.json()['data']['saude_geral'] == 'aviso'
    finally:
        app.dependency_overrides.pop(get_db, None)
