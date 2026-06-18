import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.envelope import ok
from app.core.security import criar_token
from app.services.azure_auth import extrair_usuario, validar_token_azure
from app.services.rbac import permissoes

logger = logging.getLogger('reqsys.security')

router = APIRouter(prefix='/v1/auth', tags=['Auth'])

# Mapeamento de admins conhecidos pelo prefixo do e-mail
_ADMINS = {'ericsonjosedossantos', 'admin'}

_NOMES: dict[str, str] = {
    'ericsonjosedossantos': 'Ericson Santos',
    'admin': 'Administrador',
}


def _papel_from_email(email: str) -> str:
    return 'admin' if email.split('@')[0] in _ADMINS else 'analista'


def _nome_from_email(email: str) -> str:
    prefix = email.split('@')[0]
    if prefix in _NOMES:
        return _NOMES[prefix]
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


# ─── OAuth2 PKCE code exchange (fluxo principal) ─────────────────────────────

class AzureCodeInput(BaseModel):
    code: str
    verifier: str
    redirectUri: str


_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'


@router.post('/azure-code')
def login_azure_code(body: AzureCodeInput, request: Request):
    """Recebe o authorization code do PKCE flow e faz o exchange com Azure AD."""
    if not settings.azure_tenant_id or not settings.azure_client_id:
        raise HTTPException(503, 'Azure AD não configurado')

    url = _TOKEN_URL.format(tenant=settings.azure_tenant_id)
    try:
        resp = httpx.post(url, data={
            'client_id':     settings.azure_client_id,
            'code':          body.code,
            'code_verifier': body.verifier,
            'redirect_uri':  body.redirectUri,
            'grant_type':    'authorization_code',
            'scope':         'openid profile email',
        }, timeout=15)
    except httpx.RequestError as exc:
        logger.error('azure_code_exchange_network_error: %s', exc)
        raise HTTPException(502, 'Falha de rede ao contactar Azure AD')

    if not resp.is_success:
        err = resp.json().get('error_description') or resp.text
        logger.warning('azure_code_exchange_failed ip=%s err=%s',
                       request.client.host if request.client else '?', err)
        raise HTTPException(401, f'Token exchange falhou: {err}')

    tokens = resp.json()
    id_token_raw = tokens.get('id_token')
    if not id_token_raw:
        raise HTTPException(401, 'id_token ausente na resposta do Azure AD')

    try:
        claims = validar_token_azure(id_token_raw, settings.azure_tenant_id, settings.azure_client_id)
    except Exception as exc:
        raise HTTPException(401, f'ID token inválido: {exc}')

    info  = extrair_usuario(claims)
    email = info['email']
    nome  = info['nome']
    papel = _papel_from_email(email)

    logger.info('azure_pkce_login ip=%s email=%s papel=%s',
                request.client.host if request.client else '?', email, papel)
    usuario = {'email': email, 'nome': nome, 'papel': papel, 'permissoes': permissoes(papel)}
    token   = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})


# ─── Config pública (sem autenticação) ────────────────────────────────────────

@router.get('/config')
def auth_config():
    """Retorna configuração pública do Azure AD para o frontend."""
    return ok({
        'azure_enabled': bool(settings.azure_tenant_id and settings.azure_client_id),
        'azure_tenant_id': settings.azure_tenant_id or None,
        'azure_client_id': settings.azure_client_id or None,
        'demo_login_enabled': bool(settings.allow_demo_login and not settings.is_production),
    })


# ─── Login demo (mantido somente para desenvolvimento controlado) ─────────────

class LoginInput(BaseModel):
    email: EmailStr = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
    senha: str | None = None


@router.post('/login')
def login(body: LoginInput, request: Request):
    """Login demo — permitido apenas quando ALLOW_DEMO_LOGIN=true e fora de produção."""
    if settings.is_production or not settings.allow_demo_login:
        logger.warning('demo_login_bloqueado ip=%s environment=%s', request.client.host if request.client else '?', settings.app_environment)
        raise HTTPException(403, 'Login demo desabilitado neste ambiente')

    email = body.email
    papel = _papel_from_email(email)
    logger.info('demo_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', email, papel)
    usuario = {'email': email, 'nome': _nome_from_email(email), 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})
