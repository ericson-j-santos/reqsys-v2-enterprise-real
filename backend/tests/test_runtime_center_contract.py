from fastapi.testclient import TestClient

from app.main import app


def test_runtime_center_health_endpoint_expoe_capabilities():
    response = TestClient(app).get('/monitoramento-operacional/runtime/health')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'SAUDAVEL'
    assert body['correlation_id']
    assert 'runtime-intelligence' in body['capabilities']


def test_runtime_center_diagnostico_retorna_acao_governada():
    sinais = [
        {
            'nome': 'api',
            'sucesso': True,
            'latencia_ms': 120,
            'retries': 0,
            'falhas_consecutivas': 0,
            'criticidade': 'alta',
        }
    ]

    response = TestClient(app).post('/monitoramento-operacional/runtime/diagnostico', json=sinais)

    assert response.status_code == 200
    body = response.json()
    assert body['correlation_id']
    assert body['diagnostico']['status'] == 'SAUDAVEL'
    assert body['acao_recomendada']['acao'] == 'CONTINUAR_MONITORAMENTO'
