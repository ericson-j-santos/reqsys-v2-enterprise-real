from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
_bearer = HTTPBearer(auto_error=False)


def criar_token(payload: dict, minutos: int | None = None):
    agora = datetime.now(timezone.utc)
    dados = payload.copy()
    ttl_minutes = settings.jwt_exp_minutes if minutos is None else minutos
    dados['iat'] = agora
    dados['exp'] = agora + timedelta(minutes=ttl_minutes)

    if settings.jwt_issuer:
        dados['iss'] = settings.jwt_issuer
    if settings.jwt_audience:
        dados['aud'] = settings.jwt_audience

    return jwt.encode(dados, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _jwt_decode_kwargs() -> dict:
    kwargs: dict = {
        'algorithms': [settings.jwt_algorithm],
        'options': {
            'verify_signature': True,
            'verify_exp': True,
            'verify_iat': True,
            'verify_iss': bool(settings.jwt_issuer),
            'verify_aud': bool(settings.jwt_audience),
        },
    }

    if settings.jwt_issuer:
        kwargs['issuer'] = settings.jwt_issuer
    if settings.jwt_audience:
        kwargs['audience'] = settings.jwt_audience

    return kwargs


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token não fornecido')
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            **_jwt_decode_kwargs(),
        )
        return payload
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido ou expirado')


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get('papel') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso restrito a administradores')
    return user
