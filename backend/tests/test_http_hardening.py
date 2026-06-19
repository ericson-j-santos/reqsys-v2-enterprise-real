"""
Testes de hardening HTTP e health checks operacionais.

Cobertura mínima:
- liveness;
- readiness;
- propagation de correlation_id;
- headers defensivos HTTP.
"""


def test_health_live_retorna_status_alive(client):
    resp = client.get('/health/live')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['status'] == 'alive'
    assert body['data']['service'] == 'reqsys-api'


def test_health_ready_retorna_checks_de_prontidao(client):
    resp = client.get('/health/ready')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['status'] in {'ready', 'degraded'}
    assert 'checks' in body['data']
    assert 'database' in body['data']['checks']


def test_correlation_id_e_headers_de_seguranca(client):
    correlation_id = 'corr-http-hardening-001'

    resp = client.get('/health/live', headers={'X-Correlation-ID': correlation_id})

    assert resp.status_code == 200
    assert resp.headers['X-Correlation-ID'] == correlation_id
    assert resp.headers['X-Request-ID'] == correlation_id
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'DENY'
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert 'camera=()' in resp.headers['Permissions-Policy']
