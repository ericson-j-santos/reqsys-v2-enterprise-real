import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr
from app.core.envelope import ok
from app.core.security import criar_token
from app.services.rbac import permissoes

logger = logging.getLogger('reqsys.security')

router = APIRouter(prefix='/v1/auth', tags=['Auth'])

_NOMES_CONHECIDOS: dict[str, str] = {
    'ericsonjosedossantos': 'Ericson Santos',
    'admin': 'Administrador',
}


def _nome_from_email(email: str) -> str:
    prefix = email.split('@')[0]
    if prefix in _NOMES_CONHECIDOS:
        return _NOMES_CONHECIDOS[prefix]
    parts = prefix.replace('.', ' ').replace('_', ' ').replace('-', ' ').split()
    return ' '.join(p.capitalize() for p in parts) if len(parts) > 1 else prefix.capitalize()


class LoginInput(BaseModel):
    email: EmailStr = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
    senha: str | None = None


@router.post('/login')
def login(body: LoginInput, request: Request):
    email = body.email
    papel = 'admin' if (email.startswith('admin') or email.startswith('ericsonjosedossantos')) else 'analista'
    logger.info('login ip=%s email=%s papel=%s', request.client.host, email, papel)
    usuario = {'email': email, 'nome': _nome_from_email(email), 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})

