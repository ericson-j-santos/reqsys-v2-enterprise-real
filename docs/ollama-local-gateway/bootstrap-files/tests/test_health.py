from fastapi.testclient import TestClient

from reqsys_ollama_gateway.app import app
from reqsys_ollama_gateway.config import load_settings


def test_load_settings_defaults() -> None:
    settings = load_settings()
    assert settings.env == 'dev'
    assert settings.auth_required is True
    assert settings.ollama_base_url.startswith('http')


def test_health_retorna_correlation_id() -> None:
    client = TestClient(app)
    resposta = client.get('/health', headers={'X-Correlation-Id': 'corr-test-001'})
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['status'] == 'ok'
    assert dados['correlation_id'] == 'corr-test-001'
    assert dados['service'] == 'reqsys-ollama-local-gateway'
