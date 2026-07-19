import json
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Header
from fastapi import HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.core.security import require_admin
from app.core.service_tokens import hash_token
from app.db import get_db
from app.models.service_token import ServiceToken
from app.services.auditoria import registrar_evento

router = APIRouter(prefix='/v1/admin/service-tokens', tags=['Service Tokens'])


class CriarServiceTokenPayload(BaseModel):
    label: str
    scopes: list[str]
    expires_in_days: int | None = None

    @field_validator('label')
    @classmethod
    def label_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Label não pode ser vazio')
        return v.strip()

    @field_validator('scopes')
    @classmethod
    def scopes_nao_vazio(cls, v: list[str]) -> list[str]:
        limpo = [s.strip() for s in v if s.strip()]
        if not limpo:
            raise ValueError('Informe ao menos um escopo (ex: "teams_gateway:promover_solution" ou "*")')
        return limpo

    @field_validator('expires_in_days')
    @classmethod
    def expires_positivo(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError('expires_in_days deve ser positivo quando informado')
        return v


def _auditar(db: Session, correlation_id: str | None, ator: str, acao: str, entidade_id: str, extra: dict | None = None) -> None:
    registrar_evento(db, correlation_id or 'sem-correlation-id', ator, acao, 'service_token', entidade_id, json.dumps(extra or {}, ensure_ascii=False))


@router.post('')
def criar_service_token(
    payload: CriarServiceTokenPayload,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Cria um token S2S escopado para autenticar automações em rotas admin. O token em claro só é retornado aqui."""
    token_bruto = token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else None
    )
    registro = ServiceToken(
        label=payload.label,
        token_hash=hash_token(token_bruto),
        scopes=json.dumps(payload.scopes),
        expires_at=expires_at,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'SERVICE_TOKEN_CRIADO', str(registro.id), {'label': payload.label, 'scopes': payload.scopes})
    return ok({
        'id': registro.id,
        'label': registro.label,
        'token': token_bruto,
        'scopes': payload.scopes,
        'expira_em': expires_at.isoformat() if expires_at else None,
        'aviso': 'Guarde este token agora — ele não será mostrado novamente.',
    })


@router.get('', dependencies=[Depends(require_admin)])
def listar_service_tokens(db: Session = Depends(get_db)):
    """Lista tokens de serviço sem expor o valor do token."""
    tokens = db.query(ServiceToken).order_by(ServiceToken.created_at.desc()).all()
    return ok({
        'tokens': [
            {
                'id': t.id,
                'label': t.label,
                'scopes': json.loads(t.scopes),
                'criado_em': t.created_at.isoformat() if t.created_at else None,
                'expira_em': t.expires_at.isoformat() if t.expires_at else None,
                'ultimo_uso_em': t.last_used_at.isoformat() if t.last_used_at else None,
                'revogado': t.revoked_at is not None,
            }
            for t in tokens
        ],
    })


@router.delete('/{token_id}')
def revogar_service_token(
    token_id: int,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None),
):
    """Revoga um token de serviço (idempotente)."""
    registro = db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail='Token não encontrado')
    if registro.revoked_at is None:
        registro.revoked_at = datetime.now(timezone.utc)
        db.add(registro)
        db.commit()
    _auditar(db, x_correlation_id, user.get('sub', 'admin'), 'SERVICE_TOKEN_REVOGADO', str(token_id), {'label': registro.label})
    return ok({'id': token_id, 'revogado': True})
