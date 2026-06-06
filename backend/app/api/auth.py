import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from app.core.config import settings
from app.core.envelope import ok
from app.core.security import criar_token
from app.services.rbac import permissoes
from app.services.azure_auth import validar_token_azure, extrair_usuario

logger = logging.getLogger('reqsys.security')

router = APIRouter(prefix='/v1/auth', tags=['Auth'])

# Mapeamento de admins conhecidos pelo prefixo do e-mail
_ADMINS = {'ericsonjosedossantos', 'admin'}


def _papel_from_email(email: str) -> str:
    return 'admin' if email.split('@')[0] in _ADMINS else 'analista'


def _nome_from_email(email: str) -> str:
    prefix = email.split('@')[0]
    parts = prefix.replace('.', ' ').replace('_', ' ').replace('-', ' ').split()
    return ' '.join(p.capitalize() for p in parts) if len(parts) > 1 else prefix.capitalize()


# ─── Azure AD (Microsoft Entra ID) ────────────────────────────────────────────

class AzureLoginInput(BaseModel):
    id_token: str


@router.post('/azure')
def login_azure(body: AzureLoginInput, request: Request):
    """Login via Azure AD — valida ID token emitido pelo Microsoft Entra ID."""
    if not settings.azure_tenant_id or not settings.azure_client_id:
        raise HTTPException(503, 'Azure AD não configurado (AZURE_TENANT_ID / AZURE_CLIENT_ID ausentes)')

    try:
        claims = validar_token_azure(body.id_token, settings.azure_tenant_id, settings.azure_client_id)
    except Exception as exc:
        logger.warning('azure_login_falhou ip=%s erro=%s', request.client.host if request.client else '?', exc)
        raise HTTPException(401, f'Token Azure AD inválido: {exc}')

    info = extrair_usuario(claims)
    email = info['email']
    nome = info['nome']
    papel = _papel_from_email(email)

    logger.info('azure_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', email, papel)
    usuario = {'email': email, 'nome': nome, 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})


# ─── Config pública (sem autenticação) ────────────────────────────────────────

@router.get('/config')
def auth_config():
    """Retorna configuração pública do Azure AD para o frontend."""
    return ok({
        'azure_enabled': bool(settings.azure_tenant_id and settings.azure_client_id),
        'azure_tenant_id': settings.azure_tenant_id or None,
        'azure_client_id': settings.azure_client_id or None,
    })


# ─── Login demo (mantido para desenvolvimento) ────────────────────────────────

class LoginInput(BaseModel):
    email: EmailStr = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
    senha: str | None = None


@router.post('/login')
def login(body: LoginInput, request: Request):
    """Login demo — sem validação de senha (apenas para desenvolvimento)."""
    email = body.email
    papel = _papel_from_email(email)
    logger.info('demo_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', email, papel)
    usuario = {'email': email, 'nome': _nome_from_email(email), 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})

