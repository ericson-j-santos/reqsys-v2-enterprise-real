import pytest
import jwt

from app.core.config import Settings
from app.core import security


_SECURE_SECRET = 'reqsys-ci-secret-with-at-least-thirty-two-characters'
_SECURE_AZURE_TENANT_ID = '00000000-0000-0000-0000-000000000001'
_SECURE_AZURE_CLIENT_ID = '00000000-0000-0000-0000-000000000002'


def test_production_gate_blocks_insecure_defaults(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('JWT_SECRET', 'trocar-em-producao')
    monkeypatch.setenv('JWT_ISSUER', '')
    monkeypatch.setenv('JWT_AUDIENCE', '')
    monkeypatch.setenv('ALLOW_DEMO_LOGIN', 'true')
    monkeypatch.setenv('CORS_ORIGINS', '*')

    settings = Settings()

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_production_gates()

    mensagem = str(exc_info.value)
    assert 'JWT_SECRET fraco' in mensagem
    assert 'CORS_ORIGINS não pode conter *' in mensagem
    assert 'JWT_ISSUER é obrigatório' in mensagem
    assert 'JWT_AUDIENCE é obrigatório' in mensagem
    assert 'ALLOW_DEMO_LOGIN deve ser false' in mensagem
    assert 'Azure AD obrigatório em produção' in mensagem


def test_production_gate_allows_secure_configuration(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('JWT_SECRET', _SECURE_SECRET)
    monkeypatch.setenv('JWT_ISSUER', 'reqsys-api')
    monkeypatch.setenv('JWT_AUDIENCE', 'reqsys-frontend')
    monkeypatch.setenv('ALLOW_DEMO_LOGIN', 'false')
    monkeypatch.setenv('CORS_ORIGINS', 'https://tieriprod.duckdns.org')
    monkeypatch.setenv('AZURE_TENANT_ID', _SECURE_AZURE_TENANT_ID)
    monkeypatch.setenv('AZURE_CLIENT_ID', _SECURE_AZURE_CLIENT_ID)

    settings = Settings()

    settings.validate_production_gates()
    assert settings.is_production is True
    assert settings.is_jwt_secret_weak is False
    assert settings.azure_configured is True


def test_criar_token_includes_issuer_and_audience(monkeypatch):
    monkeypatch.setattr(security.settings, 'jwt_secret', _SECURE_SECRET)
    monkeypatch.setattr(security.settings, 'jwt_algorithm', 'HS256')
    monkeypatch.setattr(security.settings, 'jwt_issuer', 'reqsys-api')
    monkeypatch.setattr(security.settings, 'jwt_audience', 'reqsys-frontend')
    monkeypatch.setattr(security.settings, 'jwt_exp_minutes', 5)

    token = security.criar_token({'sub': 'analista@reqsys.local', 'papel': 'analista'})

    payload = jwt.decode(
        token,
        _SECURE_SECRET,
        algorithms=['HS256'],
        issuer='reqsys-api',
        audience='reqsys-frontend',
    )

    assert payload['sub'] == 'analista@reqsys.local'
    assert payload['papel'] == 'analista'
    assert payload['iss'] == 'reqsys-api'
    assert payload['aud'] == 'reqsys-frontend'
