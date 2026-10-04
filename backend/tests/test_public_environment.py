from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_auth_config_usa_public_environment_sem_acionar_gate_operacional():
    original_app_env = settings.app_environment
    original_public_env = settings.public_environment
    settings.app_environment = 'development'
    settings.public_environment = 'production'
    try:
        response = client.get('/v1/auth/config')
        assert response.status_code == 200
        assert response.json()['data']['environment'] == 'producao'
        assert settings.is_production is False
    finally:
        settings.app_environment = original_app_env
        settings.public_environment = original_public_env
