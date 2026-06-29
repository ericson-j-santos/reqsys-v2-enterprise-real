from fastapi.testclient import TestClient

from app.main import app


class _FakeResponse:
    status_code = 200
    text = '{"ok": true}'

    def raise_for_status(self):
        return None

    def json(self):
        return {'ok': True, 'protocolo': 'SIMULADO-001'}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, *args, **kwargs):
        return _FakeResponse()


def test_async_httpx_job_enfileira_processa_e_permite_consulta(monkeypatch):
    import app.services.async_workflow_jobs as async_jobs

    monkeypatch.setattr(async_jobs.httpx, 'AsyncClient', _FakeAsyncClient)

    client = TestClient(app)
    response = client.post(
        '/v1/webhooks/async-httpx/jobs',
        json={
            'origem': 'power_automate',
            'destino_url': 'https://api.exemplo.com/respostas',
            'metodo': 'POST',
            'payload': {'requisito_id': 'REQ-001', 'status': 'aprovado'},
            'headers': {'Authorization': 'Bearer segredo-nao-propagado'},
            'max_attempts': 1,
        },
        headers={'X-Correlation-Id': 'test-async-correlation'},
    )

    assert response.status_code == 202
    envelope = response.json()
    assert envelope['success'] is True
    data = envelope['data']
    assert data['status'] == 'queued'
    assert data['correlation_id'] == 'test-async-correlation'

    status_response = client.get(data['status_url'])
    assert status_response.status_code == 200
    status_envelope = status_response.json()
    status_data = status_envelope['data']
    assert status_data['status'] == 'completed'
    assert status_data['attempts'] == 1
    assert status_data['response_status_code'] == 200
    assert status_data['response_payload']['protocolo'] == 'SIMULADO-001'


def test_async_httpx_health_retorna_backend_de_fila_atual():
    client = TestClient(app)
    response = client.get('/v1/webhooks/async-httpx/health')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'ok'
    assert data['queue_backend'] == 'in_memory'
    assert 'azure_service_bus' in data['enterprise_upgrade_path']
