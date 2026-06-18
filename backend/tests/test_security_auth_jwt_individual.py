from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security

_SECURE_SECRET = 'reqsys-ci-secret-with-at-least-thirty-two-characters'


def _configure_jwt_settings(monkeypatch, issuer: str = 'reqsys-api', audience: str = 'reqsys-frontend') -> None:
    monkeypatch.setattr(security.settings, 'jwt_secret', _SECURE_SECRET)
    monkeypatch.setattr(security.settings, 'jwt_algorithm', 'HS256')
    monkeypatch.setattr(security.settings, 'jwt_issuer', issuer)
    monkeypatch.setattr(security.settings, 'jwt_audience', audience)
    monkeypatch.setattr(security.settings, 'jwt_exp_minutes', 60)


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)


def _encode_token(**claims) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': 'analista@reqsys.local',
        'papel': 'analista',
        'iat': now,
        'exp': now + timedelta(minutes=5),
        'iss': 'reqsys-api',
        'aud': 'reqsys-frontend',
    }
    payload.update(claims)
    return jwt.encode(payload, _SECURE_SECRET, algorithm='HS256')


def test_criar_token_respeita_minutos_zero_sem_fallback_para_default(monkeypatch):
    _configure_jwt_settings(monkeypatch)

    token = security.criar_token({'sub': 'analista@reqsys.local'}, minutos=0)

    payload = jwt.decode(
        token,
        _SECURE_SECRET,
        algorithms=['HS256'],
        options={'verify_exp': False, 'verify_iat': False, 'verify_aud': False},
    )
    assert payload['exp'] == payload['iat']


def test_decode_rejeita_issuer_incorreto(monkeypatch):
    _configure_jwt_settings(monkeypatch)
    token = _encode_token(iss='issuer-invalido')

    with pytest.raises(HTTPException) as exc_info:
        security.get_current_user(_credentials(token))

    assert exc_info.value.status_code == 401


def test_decode_rejeita_audience_incorreta(monkeypatch):
    _configure_jwt_settings(monkeypatch)
    token = _encode_token(aud='audience-invalida')

    with pytest.raises(HTTPException) as exc_info:
        security.get_current_user(_credentials(token))

    assert exc_info.value.status_code == 401


def test_decode_aceita_issuer_e_audience_validos(monkeypatch):
    _configure_jwt_settings(monkeypatch)
    token = _encode_token()

    user = security.get_current_user(_credentials(token))

    assert user['sub'] == 'analista@reqsys.local'
    assert user['iss'] == 'reqsys-api'
    assert user['aud'] == 'reqsys-frontend'


def test_decode_rejeita_token_expirado(monkeypatch):
    _configure_jwt_settings(monkeypatch)
    now = datetime.now(timezone.utc)
    token = _encode_token(iat=now - timedelta(minutes=10), exp=now - timedelta(minutes=1))

    with pytest.raises(HTTPException) as exc_info:
        security.get_current_user(_credentials(token))

    assert exc_info.value.status_code == 401
