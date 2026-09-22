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


def test_lowcode_package_padrao_restrito_nao_exige_dataverse_admin_ou_api(auth_override):
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/lowcode/package',
        json={},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['profile'] == 'copilot_memory_corporativo_restrito'
    assert data['package']['zip_base64']
    assert data['governance']['requires_custom_memory_api'] is False
    assert data['governance']['requires_dataverse'] is False
    assert data['governance']['requires_powerapps_admin'] is False
    assert data['dataverse']['tables'] == []
    assert data['apps']['canvas_app'] == {}
    assert data['custom_connector'] == {}


def test_lowcode_package_com_api_retorna_sem_powerapp_e_dataverse(auth_override):
    response = client.post(
        '/v1/hub-lowcode/copilot-memory/lowcode/package',
        json={
            'profile': 'copilot_memory_corporativo_com_api',
            'solution_name': 'CopilotMemoryCorp',
            'display_name': 'Copilot Memory Corp',
            'target_environment': 'dev',
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['profile'] == 'copilot_memory_corporativo_com_api'
    assert data['governance']['requires_custom_memory_api'] is True
    assert data['dataverse']['tables'] == []
    assert data['apps']['canvas_app'] == {}


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
