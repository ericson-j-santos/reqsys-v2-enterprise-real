from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def criar_token(payload: dict, minutos: int = 60):
    dados = payload.copy()
    dados['exp'] = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return jwt.encode(dados, settings.jwt_secret, algorithm=settings.jwt_algorithm)
