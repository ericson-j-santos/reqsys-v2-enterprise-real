import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import obter_correlation_id
from app.core.envelope import ok
from app.core.pii_masking import mascarar_email
from app.core.security import criar_token
from app.db import get_db
from app.services.auditoria import registrar_evento
from app.services.azure_auth import extrair_usuario, validar_token_azure
from app.services.certificate_auth import (
    CertificateAuthError,
    criar_desafio,
    validar_login_certificado,
)
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


def _demo_login_is_enabled() -> bool:
    """Resolve o gate pelo ambiente público efetivo, preservando bloqueio em produção.

    APP_ENV pode permanecer ``production`` em imagens otimizadas de DEV/STG. O ambiente
    funcional exposto deve ser determinado por PUBLIC_ENVIRONMENT quando configurado.
    """
    return bool(
        settings.allow_demo_login
        and settings.normalized_public_environment != 'producao'
    )


# ─── Azure AD (Microsoft Entra ID) ────────────────────────────────────────────

class AzureLoginInput(BaseModel):
    id_token: str


class CertificateVerifyInput(BaseModel):
    certificate_pem: str
    challenge: str
    signature_base64: str


@router.post('/azure')
def login_azure(body: AzureLoginInput, request: Request, db: Session = Depends(get_db)):
    """Login via Azure AD — valida ID token emitido pelo Microsoft Entra ID."""
    if not settings.azure_configured:
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

    logger.info('azure_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', mascarar_email(email), papel)
    registrar_evento(db, obter_correlation_id(), email, 'LOGIN_AZURE', 'usuario', email)
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
def login_azure_code(body: AzureCodeInput, request: Request, db: Session = Depends(get_db)):
    """Recebe o authorization code do PKCE flow e faz o exchange com Azure AD."""
    if not settings.azure_configured:
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
                request.client.host if request.client else '?', mascarar_email(email), papel)
    registrar_evento(db, obter_correlation_id(), email, 'LOGIN_AZURE_PKCE', 'usuario', email)
    usuario = {'email': email, 'nome': nome, 'papel': papel, 'permissoes': permissoes(papel)}
    token   = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})


# ─── Config pública (sem autenticação) ────────────────────────────────────────

# Certificado digital (fluxo hibrido)

@router.post('/certificate/challenge')
def certificate_challenge():
    """Emite desafio curto para assinatura local com certificado digital."""
    if not settings.certificate_login_enabled:
        raise HTTPException(503, 'Login com certificado digital nao configurado')
    return ok(criar_desafio(settings.certificate_challenge_ttl_seconds))


@router.post('/certificate/verify')
def certificate_verify(body: CertificateVerifyInput, request: Request, db: Session = Depends(get_db)):
    """Valida certificado + assinatura do desafio e emite JWT interno ReqSys."""
    if not settings.certificate_login_enabled:
        raise HTTPException(503, 'Login com certificado digital nao configurado')

    try:
        identidade = validar_login_certificado(
            certificate_pem=body.certificate_pem,
            challenge=body.challenge,
            signature_base64=body.signature_base64,
            allowed_issuers=settings.certificate_allowed_issuers,
            trust_store_path=settings.certificate_trust_store_path,
        )
    except CertificateAuthError as exc:
        logger.warning('certificate_login_falhou ip=%s erro=%s', request.client.host if request.client else '?', exc)
        raise HTTPException(401, str(exc))

    email = identidade.reqsys_email
    papel = _papel_from_email(email)
    usuario = {
        'email': email,
        'nome': identidade.display_name,
        'papel': papel,
        'permissoes': permissoes(papel),
        'auth_provider': 'certificate',
        'certificate_subject': identidade.subject,
        'certificate_issuer': identidade.issuer,
    }
    logger.info('certificate_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', mascarar_email(email), papel)
    registrar_evento(db, obter_correlation_id(), email, 'LOGIN_CERTIFICADO', 'usuario', email)
    token = criar_token({'sub': email, 'papel': papel, 'auth_provider': 'certificate'})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})


@router.get('/config')
def auth_config():
    """Retorna configuração pública do Azure AD para o frontend, sem expor segredo."""
    azure_enabled = settings.azure_configured
    missing_fields = settings.azure_missing_fields
    redirect_uri = settings.azure_expected_redirect_uri
    return ok({
        'azure_enabled': azure_enabled,
        'azure_tenant_id': settings.azure_tenant_id or None,
        'azure_client_id': settings.azure_client_id or None,
        'certificate_enabled': bool(settings.certificate_login_enabled),
        'certificate_mode': 'challenge-signature',
        'demo_login_enabled': _demo_login_is_enabled(),
        'environment': settings.normalized_public_environment,
        'expected_redirect_uri': redirect_uri or None,
        'auth_status': 'ready' if azure_enabled else 'misconfigured',
        'missing_fields': missing_fields,
        'operator_action': None if azure_enabled else 'Configure AZURE_TENANT_ID e AZURE_CLIENT_ID no ambiente e registre o expected_redirect_uri no Microsoft Entra ID.',
    })


# ─── Login demo (mantido somente para desenvolvimento controlado) ─────────────

class LoginInput(BaseModel):
    email: EmailStr = 'ericsonjosedossantos@tieri659.onmicrosoft.com'
    senha: str | None = None


@router.post('/login')
def login(body: LoginInput, request: Request, db: Session = Depends(get_db)):
    """Login demo — permitido quando ALLOW_DEMO_LOGIN=true e o ambiente público não é produção."""
    if not _demo_login_is_enabled():
        logger.warning(
            'demo_login_bloqueado ip=%s app_environment=%s public_environment=%s',
            request.client.host if request.client else '?',
            settings.app_environment,
            settings.normalized_public_environment,
        )
        raise HTTPException(403, 'Login demo desabilitado neste ambiente')

    email = body.email
    papel = _papel_from_email(email)
    logger.info('demo_login ip=%s email=%s papel=%s', request.client.host if request.client else '?', mascarar_email(email), papel)
    registrar_evento(db, obter_correlation_id(), email, 'LOGIN_DEMO', 'usuario', email)
    usuario = {'email': email, 'nome': _nome_from_email(email), 'papel': papel, 'permissoes': permissoes(papel)}
    token = criar_token({'sub': email, 'papel': papel})
    return ok({'access_token': token, 'token_type': 'bearer', 'usuario': usuario})
