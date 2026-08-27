import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_copilot_memory_lowcode_api.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.api.copilot_memory import require_copilot_memory_auth
from app.core.service_tokens import ServiceAuthContext
from app.main import app

client = TestClient(app)


def _fake_ctx():
    return ServiceAuthContext(ator='admin@teste', via_token=False)


@pytest.fixture
def auth_override():
    app.dependency_overrides[require_copilot_memory_auth] = _fake_ctx
    yield
    app.dependency_overrides.pop(require_copilot_memory_auth, None)


def test_lowcode_package_sem_auth_retorna_401_ou_403():
    response = client.post('/v1/hub-lowcode/copilot-memory/lowcode/package', json={})
    assert response.status_code in (401, 403)


def test_lowcode_package_minimo_retorna_zip_transportavel(auth_override):
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/lowcode/package',
        json={
            'profile': 'copilot_memory_minimal',
            'solution_name': 'CopilotMemoryCorp',
            'display_name': 'Copilot Memory Corp',
            'target_environment': 'dev',
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['profile'] == 'copilot_memory_minimal'
    assert data['package']['zip_base64']
    assert data['governance']['no_custom_reqsys_api_required'] is True
    assert data['dataverse']['tables'] == []


def test_lowcode_package_enterprise_retorna_powerapp_e_dataverse(auth_override):
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/lowcode/package',
        json={'profile': 'copilot_memory_enterprise'},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['apps']['canvas_app']['name'] == 'Copilot Memory Admin'
    assert len(data['dataverse']['tables']) == 2


def test_lowcode_package_rejeita_perfil_desconhecido(auth_override):
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/lowcode/package',
        json={'profile': 'perfil_invalido'},
    )
    assert response.status_code == 422
