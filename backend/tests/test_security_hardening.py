"""
Testes de hardening operacional e autenticação.

Cobertura mínima:
- health checks canônicos para produção;
- propagation de correlation_id;
- headers de segurança HTTP;
- JWT com issuer e audience;
- bloqueio de login demo em produção.
"""

import jwt

from app.core.config import settings
from app.core.security import criar_token


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
    correlation_id = 'corr-security-hardening-001'

    resp = client.get('/health/live', headers={'X-Correlation-ID': correlation_id})

    assert resp.status_code == 200
    assert resp.headers['X-Correlation-ID'] == correlation_id
    assert resp.headers['X-Request-ID'] == correlation_id
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'DENY'
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert 'camera=()' in resp.headers['Permissions-Policy']


def test_token_jwt_contem_issuer_e_audience():
    token = criar_token({'sub': 'usuario.teste@reqsys.local', 'papel': 'admin'})

    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=getattr(settings, 'jwt_issuer', 'reqsys-api'),
        audience=getattr(settings, 'jwt_audience', 'reqsys-web'),
    )

    assert payload['sub'] == 'usuario.teste@reqsys.local'
    assert payload['papel'] == 'admin'
    assert payload['iss'] == getattr(settings, 'jwt_issuer', 'reqsys-api')
    assert payload['aud'] == getattr(settings, 'jwt_audience', 'reqsys-web')
    assert 'iat' in payload
    assert 'exp' in payload


def test_login_demo_bloqueado_em_producao(client, monkeypatch):
    monkeypatch.setattr(settings, 'app_env', 'production', raising=False)
    monkeypatch.setattr(settings, 'allow_demo_login', False, raising=False)

    resp = client.post('/v1/auth/login', json={'email': 'analista@reqsys.local', 'senha': 'nao-validada'})

    assert resp.status_code == 403
    assert resp.json()['detail'] == 'Login demo bloqueado em produção'
