from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
_bearer = HTTPBearer(auto_error=False)


def criar_token(payload: dict, minutos: int = 60):
    dados = payload.copy()
    dados['exp'] = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return jwt.encode(dados, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token não fornecido')
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido ou expirado')


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get('papel') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Acesso restrito a administradores')
    return user
