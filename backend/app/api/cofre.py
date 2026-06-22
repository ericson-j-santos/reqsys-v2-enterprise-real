import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator

from app.core.cofre_verificador_cego import (
    CHAVE_OPERACIONAL_VERIFICADOR,
    VerificadorCegoIndisponivel,
    verificar_valor_cego,
)
from app.core.config import settings
from app.core.envelope import ok
from app.core.secrets import (
    _vault_service_name,
    delete_secret_from_vault,
    init_vault,
    read_secret_from_vault,
    vault_initialized,
    write_secret_to_vault,
)
from app.core.security import require_admin

router = APIRouter(prefix='/v1/cofre', tags=['Cofre'])

_MANAGEMENT_BLOCKED_KEYS = {'__master_key__'}
_LOOKUP_BLOCKED_KEYS = {'__master_key__', CHAVE_OPERACIONAL_VERIFICADOR}


def _check_vault_token(x_vault_token: str | None = Header(default=None)) -> None:
    """Autenticacao service-to-service via header X-Vault-Token."""
    if not settings.vault_api_token:
        raise HTTPException(status_code=503, detail='VAULT_API_TOKEN não configurado no servidor')
    if not x_vault_token:
        raise HTTPException(status_code=401, detail='Vault token inválido ou ausente')
    if not hmac.compare_digest(x_vault_token.encode('utf-8'), settings.vault_api_token.encode('utf-8')):
        raise HTTPException(status_code=401, detail='Vault token inválido ou ausente')


class GravarSegredoPayload(BaseModel):
    key: str
    value: str

    @field_validator('key')
    @classmethod
    def key_nao_reservada(cls, v: str) -> str:
        if v.strip() in _MANAGEMENT_BLOCKED_KEYS:
            raise ValueError('Chave reservada não permitida')
        if not v.strip():
            raise ValueError('Chave não pode ser vazia')
        return v.strip()

    @field_validator('value')
    @classmethod
    def value_nao_vazio(cls, v: str) -> str:
        if not v:
            raise ValueError('Valor não pode ser vazio')
        return v


class ResolverSegredoPayload(BaseModel):
    key: str


class VerificarSegredoPayload(BaseModel):
    key: str
    value: str

    @field_validator('key')
    @classmethod
    def key_nao_reservada(cls, v: str) -> str:
        if v.strip() in _LOOKUP_BLOCKED_KEYS:
            raise ValueError('Chave reservada não permitida')
        if not v.strip():
            raise ValueError('Chave não pode ser vazia')
        return v.strip()

    @field_validator('value')
    @classmethod
    def value_nao_vazio(cls, v: str) -> str:
        if not v:
            raise ValueError('Valor não pode ser vazio')
        return v


# ---------------------------------------------------------------------------
# Gestão — requer JWT admin
# ---------------------------------------------------------------------------

@router.post('/init', dependencies=[Depends(require_admin)])
def inicializar_vault(overwrite: bool = False):
    """Cria a master key no keyring do sistema. Necessário uma única vez por ambiente."""
    criado = init_vault(overwrite=overwrite)
    if not criado and not overwrite:
        return ok({
            'status': 'ja_inicializado',
            'service': _vault_service_name(),
            'mensagem': 'Vault já possui master key. Use ?overwrite=true para recriar (invalida todos os segredos existentes).',
        })
    return ok({'status': 'inicializado', 'service': _vault_service_name()})


@router.get('/status', dependencies=[Depends(require_admin)])
def status_vault():
    """Retorna se o vault está inicializado e qual service name está em uso."""
    return ok({
        'inicializado': vault_initialized(),
        'service': _vault_service_name(),
        'vault_api_token_configurado': bool(settings.vault_api_token),
    })


@router.post('/segredos', dependencies=[Depends(require_admin)])
def gravar_segredo(payload: GravarSegredoPayload):
    """Criptografa e armazena um segredo no cofre."""
    try:
        write_secret_to_vault(payload.key, payload.value)
        return ok({'key': payload.key, 'gravado': True})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete('/segredos/{key}', dependencies=[Depends(require_admin)])
def remover_segredo(key: str):
    """Remove um segredo do cofre."""
    if key in _LOOKUP_BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada não pode ser removida por esta rota')
    removido = delete_secret_from_vault(key)
    return ok({'key': key, 'removido': removido})


# ---------------------------------------------------------------------------
# Lookup service-to-service — requer X-Vault-Token header
# ---------------------------------------------------------------------------

@router.get('/segredos/{key}', dependencies=[Depends(_check_vault_token)])
def obter_segredo(key: str):
    """
    Retorna o valor de um segredo via GET.
    Ideal para scripts e aplicações: GET /v1/cofre/segredos/MINHA_CHAVE
    Autenticação via header: X-Vault-Token: <VAULT_API_TOKEN>
    """
    if key in _LOOKUP_BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada')
    value = read_secret_from_vault(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f'Segredo "{key}" não encontrado no cofre')
    return ok({'key': key, 'value': value})


@router.post('/resolver', dependencies=[Depends(_check_vault_token)])
def resolver_segredo(payload: ResolverSegredoPayload):
    """
    Retorna o valor de um segredo via POST (alias de GET /segredos/{key}).
    Autenticação via header: X-Vault-Token: <VAULT_API_TOKEN>
    """
    if payload.key in _LOOKUP_BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada')
    value = read_secret_from_vault(payload.key)
    if value is None:
        raise HTTPException(status_code=404, detail=f'Segredo "{payload.key}" não encontrado no cofre')
    return ok({'key': payload.key, 'value': value})


@router.post('/verificar', dependencies=[Depends(_check_vault_token)])
def verificar_segredo(payload: VerificarSegredoPayload):
    """
    Verifica igualdade contra um segredo do cofre sem retornar o segredo bruto.
    Retorna apenas match True/False e metadados seguros de verificacao.
    """
    value = read_secret_from_vault(payload.key)
    if value is None:
        raise HTTPException(status_code=404, detail=f'Segredo "{payload.key}" não encontrado no cofre')
    try:
        result = verificar_valor_cego(payload.key, value, payload.value)
    except VerificadorCegoIndisponivel as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return ok({
        'key': result.key,
        'match': result.match,
        'verifier_version': result.verifier_version,
        'value_exposed': result.value_exposed,
    })
