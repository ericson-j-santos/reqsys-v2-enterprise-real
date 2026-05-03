from fastapi import APIRouter
from app.core.envelope import ok
from app.core.security import criar_token
from app.services.rbac import permissoes

router = APIRouter(prefix='/v1/auth', tags=['Auth'])

@router.post('/login')
def login(payload: dict):
    email = payload.get('email', 'ericsonjosedossantos@tieri659.onmicrosoft.com')
    papel = 'admin' if (email.startswith('admin') or email.startswith('ericsonjosedossantos')) else 'analista'
    usuario = {'email': email, 'nome': 'Usuário Demo', 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})

