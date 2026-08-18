from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.correlation import obter_correlation_id
from app.core.envelope import ok
from app.core.pii_masking import mascarar_email
from app.core.security import criar_token, get_current_user, require_admin
from app.db import get_db
from app.services.auditoria import registrar_evento
from app.services.rbac import permissoes
from app.services.session_management import invalidate_all, snapshot

router = APIRouter(tags=['Session Security'])


class InvalidateAllSessionsRequest(BaseModel):
    confirmacao: str = Field(min_length=1, max_length=100)
    motivo: str = Field(min_length=8, max_length=1000)


def _confirmation_phrase() -> str:
    return 'INVALIDAR-SESSOES-PROD' if settings.is_production else 'INVALIDAR-SESSOES-DEV'


def _masked_actor(value: str | None) -> str:
    actor = (value or 'admin').strip()
    if '@' in actor:
        return mascarar_email(actor)
    return actor[:80]


def _status_payload() -> dict:
    state = snapshot()
    return {
        'environment': settings.normalized_environment,
        'session_epoch': state.session_epoch,
        'authz_version': state.authz_version,
        'invalidated_at': state.invalidated_at.isoformat() if state.invalidated_at else None,
        'invalidated_by': state.invalidated_by,
        'invalidation_reason': state.invalidation_reason,
        'correlation_id': state.correlation_id,
        'required_confirmation': _confirmation_phrase(),
        'production_touched': settings.is_production,
        'active_session_inventory': 'stateless_not_enumerated',
    }


@router.get('/v1/auth/session')
def current_session(user: dict = Depends(get_current_user)):
    state = snapshot()
    papel = str(user.get('papel') or '')
    return ok({
        'papel': papel,
        'permissoes': permissoes(papel),
        'session_epoch': state.session_epoch,
        'authz_version': state.authz_version,
        'auth_provider': user.get('auth_provider'),
    })


@router.post('/v1/auth/session/refresh')
def refresh_session(user: dict = Depends(get_current_user)):
    papel = str(user.get('papel') or '')
    token_payload = {
        'sub': user.get('sub'),
        'papel': papel,
    }
    if user.get('auth_provider'):
        token_payload['auth_provider'] = user.get('auth_provider')

    access_token = criar_token(token_payload)
    state = snapshot()
    return ok({
        'access_token': access_token,
        'token_type': 'bearer',
        'usuario': {
            'papel': papel,
            'permissoes': permissoes(papel),
            'session_epoch': state.session_epoch,
            'authz_version': state.authz_version,
        },
    })


@router.get('/v1/admin/security/sessions/status')
def sessions_status(_: dict = Depends(require_admin)):
    return ok(_status_payload())


@router.post('/v1/admin/security/sessions/invalidate-all')
def invalidate_all_sessions(
    body: InvalidateAllSessionsRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    expected = _confirmation_phrase()
    if body.confirmacao != expected:
        raise HTTPException(status_code=409, detail=f'Confirmação inválida. Informe exatamente {expected}.')

    correlation_id = obter_correlation_id()
    actor = _masked_actor(user.get('sub'))
    state = invalidate_all(
        actor=actor,
        reason=body.motivo,
        correlation_id=correlation_id,
        db=db,
    )
    registrar_evento(
        db,
        correlation_id,
        actor,
        'INVALIDAR_TODAS_SESSOES',
        'security_session_state',
        str(state.session_epoch),
    )

    payload = _status_payload()
    payload['decision'] = 'all_human_sessions_invalidated'
    return ok(payload)
