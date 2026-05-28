import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr
from app.core.envelope import ok
from app.core.security import criar_token
from app.services.rbac import permissoes

logger = logging.getLogger('reqsys.security')

router = APIRouter(prefix='/v1/auth', tags=['Auth'])


class LoginInput(BaseModel):
    email: EmailStr = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
    senha: str | None = None


@router.post('/login')
def login(body: LoginInput, request: Request):
    email = body.email
    papel = 'admin' if (email.startswith('admin') or email.startswith('ericsonjosedossantos')) else 'analista'
    logger.info('login ip=%s email=%s papel=%s', request.client.host, email, papel)
    usuario = {'email': email, 'nome': 'Usuário Demo', 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})

