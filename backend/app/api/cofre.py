import hashlib
import json
from datetime import datetime, timezone
from fnmatch import fnmatch
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

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
from app.db import get_db
from app.models.vault_token import VaultToken
from app.services.auditoria import registrar_evento

router = APIRouter(prefix='/v1/cofre', tags=['Cofre'])

_BLOCKED_KEYS = {'__master_key__'}


class GravarSegredoPayload(BaseModel):
    key: str
    value: str

    @field_validator('key')
    @classmethod
    def key_nao_reservada(cls, v: str) -> str:
        if v.strip() in _BLOCKED_KEYS:
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


class CriarTokenPayload(BaseModel):
    label: str
    key_patterns: list[str]

    @field_validator('label')
    @classmethod
    def label_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Label não pode ser vazio')
        return v.strip()

    @field_validator('key_patterns')
    @classmethod
    def patterns_nao_vazio(cls, v: list[str]) -> list[str]:
        limpo = [p.strip() for p in v if p.strip()]
        if not limpo:
            raise ValueError('Informe ao menos um padrão de chave (ex: "MEUPROJETO_*")')
        return limpo


# ---------------------------------------------------------------------------
# Auditoria — helper interno (nunca loga o valor do segredo, ADR-002)
# ---------------------------------------------------------------------------

def _auditar(db: Session, correlation_id: str | None, ator: str, acao: str, key: str, extra: dict | None = None) -> None:
    registrar_evento(
        db,
        correlation_id or 'sem-correlation-id',
        ator,
        acao,
        'cofre_segredo',
        key,
        json.dumps(extra or {}, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# Autenticação S2S — token global legado ou token escopado por consumidor
# ---------------------------------------------------------------------------

class VaultTokenContext:
    def __init__(self, ator: str, key_patterns: list[str] | None):
        self.ator = ator
        self.key_patterns = key_patterns  # None = token legado global, sem restrição de escopo


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _resolve_scoped_token(db: Session, token_hash: str) -> VaultToken | None:
    return (
        db.query(VaultToken)
        .filter(VaultToken.token_hash == token_hash, VaultToken.revoked_at.is_(None))
        .first()
    )


def _check_vault_token(
    x_vault_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> VaultTokenContext:
    """Autenticação service-to-service via header X-Vault-Token.

    Tenta primeiro um token escopado por consumidor (`VaultToken`); cai para o
    token global legado (`VAULT_API_TOKEN`) só se nenhum token escopado casar —
    o uso do modo legado é auditado para permitir migração gradual.
    """
    if x_vault_token:
        scoped = _resolve_scoped_token(db, _hash_token(x_vault_token))
        if scoped:
            scoped.last_used_at = datetime.now(timezone.utc)
            db.add(scoped)
            db.commit()
            return VaultTokenContext(ator=f'token:{scoped.label}', key_patterns=json.loads(scoped.key_patterns))

    if not settings.vault_api_token:
        raise HTTPException(status_code=503, detail='VAULT_API_TOKEN não configurado no servidor')
    if not x_vault_token or x_vault_token != settings.vault_api_token:
        raise HTTPException(status_code=401, detail='Vault token inválido ou ausente')

    _auditar(db, None, 'token-legado-global', 'COFRE_TOKEN_LEGADO_USADO', 'global')
    return VaultTokenContext(ator='token-legado-global', key_patterns=None)


def _exigir_escopo(ctx: VaultTokenContext, key: str) -> None:
    if ctx.key_patterns is None:
        return
    if not any(fnmatch(key, padrao) for padrao in ctx.key_patterns):
        raise HTTPException(status_code=403, detail=f'Token sem escopo para a chave "{key}"')


# ---------------------------------------------------------------------------
# Gestão — requer JWT admin
# ---------------------------------------------------------------------------

@router.post('/init')
def inicializar_vault(
    overwrite: bool = False,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Cria a master key no keyring do sistema. Necessário uma única vez por ambiente."""
    criado = init_vault(overwrite=overwrite)
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'COFRE_INICIALIZADO', 'global', {'overwrite': overwrite, 'criado': criado})
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


@router.post('/segredos')
def gravar_segredo(
    payload: GravarSegredoPayload,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Criptografa e armazena um segredo no cofre."""
    try:
        write_secret_to_vault(payload.key, payload.value)
        _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'COFRE_SEGREDO_GRAVADO', payload.key)
        return ok({'key': payload.key, 'gravado': True})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete('/segredos/{key}')
def remover_segredo(
    key: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Remove um segredo do cofre."""
    if key in _BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada não pode ser removida por esta rota')
    removido = delete_secret_from_vault(key)
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'COFRE_SEGREDO_REMOVIDO', key, {'removido': removido})
    return ok({'key': key, 'removido': removido})


# ---------------------------------------------------------------------------
# Tokens escopados — requer JWT admin
# ---------------------------------------------------------------------------

@router.post('/tokens')
def criar_token(
    payload: CriarTokenPayload,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Cria um token S2S escopado a um conjunto de padrões de chave. O token em claro só é retornado aqui."""
    token_bruto = token_urlsafe(32)
    registro = VaultToken(label=payload.label, token_hash=_hash_token(token_bruto), key_patterns=json.dumps(payload.key_patterns))
    db.add(registro)
    db.commit()
    db.refresh(registro)
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'COFRE_TOKEN_CRIADO', payload.label, {'id': registro.id, 'key_patterns': payload.key_patterns})
    return ok({
        'id': registro.id,
        'label': registro.label,
        'token': token_bruto,
        'key_patterns': payload.key_patterns,
        'aviso': 'Guarde este token agora — ele não será mostrado novamente.',
    })


@router.get('/tokens', dependencies=[Depends(require_admin)])
def listar_tokens(db: Session = Depends(get_db)):
    """Lista tokens escopados sem expor o valor do token."""
    tokens = db.query(VaultToken).order_by(VaultToken.created_at.desc()).all()
    return ok({
        'tokens': [
            {
                'id': t.id,
                'label': t.label,
                'key_patterns': json.loads(t.key_patterns),
                'criado_em': t.created_at.isoformat() if t.created_at else None,
                'ultimo_uso_em': t.last_used_at.isoformat() if t.last_used_at else None,
                'revogado': t.revoked_at is not None,
            }
            for t in tokens
        ],
    })


@router.delete('/tokens/{token_id}')
def revogar_token(
    token_id: int,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Revoga um token escopado (idempotente)."""
    registro = db.query(VaultToken).filter(VaultToken.id == token_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail='Token não encontrado')
    if registro.revoked_at is None:
        registro.revoked_at = datetime.now(timezone.utc)
        db.add(registro)
        db.commit()
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'COFRE_TOKEN_REVOGADO', registro.label, {'id': token_id})
    return ok({'id': token_id, 'revogado': True})


# ---------------------------------------------------------------------------
# Lookup service-to-service — requer X-Vault-Token header (global legado ou escopado)
# ---------------------------------------------------------------------------

@router.get('/segredos/{key}')
def obter_segredo(
    key: str,
    ctx: VaultTokenContext = Depends(_check_vault_token),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """
    Retorna o valor de um segredo via GET.
    Ideal para scripts e aplicações: GET /v1/cofre/segredos/MINHA_CHAVE
    Autenticação via header: X-Vault-Token: <VAULT_API_TOKEN ou token escopado>
    """
    if key in _BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada')
    _exigir_escopo(ctx, key)
    value = read_secret_from_vault(key)
    if value is None:
        _auditar(db, x_correlation_id, ctx.ator, 'COFRE_SEGREDO_LIDO_FALHA', key)
        raise HTTPException(status_code=404, detail=f'Segredo "{key}" não encontrado no cofre')
    _auditar(db, x_correlation_id, ctx.ator, 'COFRE_SEGREDO_LIDO', key)
    return ok({'key': key, 'value': value})


@router.post('/resolver')
def resolver_segredo(
    payload: ResolverSegredoPayload,
    ctx: VaultTokenContext = Depends(_check_vault_token),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """
    Retorna o valor de um segredo via POST (alias de GET /segredos/{key}).
    Autenticação via header: X-Vault-Token: <VAULT_API_TOKEN ou token escopado>
    """
    if payload.key in _BLOCKED_KEYS:
        raise HTTPException(status_code=400, detail='Chave reservada')
    _exigir_escopo(ctx, payload.key)
    value = read_secret_from_vault(payload.key)
    if value is None:
        _auditar(db, x_correlation_id, ctx.ator, 'COFRE_SEGREDO_LIDO_FALHA', payload.key)
        raise HTTPException(status_code=404, detail=f'Segredo "{payload.key}" não encontrado no cofre')
    _auditar(db, x_correlation_id, ctx.ator, 'COFRE_SEGREDO_LIDO', payload.key)
    return ok({'key': payload.key, 'value': value})
