from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.security_session_state import SecuritySessionState
from app.services.rbac import PERMISSOES_EXTRA_PADRAO, PERMISSOES_POR_PAPEL


@dataclass(frozen=True)
class SessionSecuritySnapshot:
    session_epoch: int
    authz_version: str
    invalidated_at: datetime | None
    invalidated_by: str | None
    invalidation_reason: str | None
    correlation_id: str | None


def current_authz_version() -> str:
    extra = {
        papel.value: sorted(escopos)
        for papel, escopos in PERMISSOES_EXTRA_PADRAO.items()
    }
    material = json.dumps(
        {
            'legacy': {papel: sorted(escopos) for papel, escopos in PERMISSOES_POR_PAPEL.items()},
            'extra': extra,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    return f'rbac-{hashlib.sha256(material).hexdigest()[:16]}'


def _get_or_create(db: Session) -> SecuritySessionState:
    state = db.get(SecuritySessionState, 1)
    if state is not None:
        return state

    state = SecuritySessionState(id=1, session_epoch=0)
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def snapshot(db: Session | None = None) -> SessionSecuritySnapshot:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        state = _get_or_create(session)
        return SessionSecuritySnapshot(
            session_epoch=state.session_epoch,
            authz_version=current_authz_version(),
            invalidated_at=state.invalidated_at,
            invalidated_by=state.invalidated_by,
            invalidation_reason=state.invalidation_reason,
            correlation_id=state.correlation_id,
        )
    finally:
        if owns_session:
            session.close()


def invalidate_all(
    *,
    actor: str,
    reason: str,
    correlation_id: str,
    db: Session | None = None,
) -> SessionSecuritySnapshot:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        state = _get_or_create(session)
        state.session_epoch += 1
        state.invalidated_at = datetime.now(UTC)
        state.invalidated_by = actor[:200]
        state.invalidation_reason = reason[:1000]
        state.correlation_id = correlation_id[:120]
        session.add(state)
        session.commit()
        session.refresh(state)
        return SessionSecuritySnapshot(
            session_epoch=state.session_epoch,
            authz_version=current_authz_version(),
            invalidated_at=state.invalidated_at,
            invalidated_by=state.invalidated_by,
            invalidation_reason=state.invalidation_reason,
            correlation_id=state.correlation_id,
        )
    finally:
        if owns_session:
            session.close()


def token_security_claims() -> dict[str, object]:
    state = snapshot()
    return {
        'session_epoch': state.session_epoch,
        'authz_version': state.authz_version,
    }


def validate_token_security(payload: dict) -> tuple[bool, str | None]:
    state = snapshot()
    token_epoch = int(payload.get('session_epoch', 0) or 0)
    if token_epoch < state.session_epoch:
        return False, 'SESSION_REVOKED'

    token_authz = payload.get('authz_version')
    # Tokens legados são aceitos até o primeiro reset global. Depois disso,
    # session_epoch > 0 já os invalida. Novos tokens passam a carregar versão.
    if token_authz and token_authz != state.authz_version:
        return False, 'AUTHORIZATION_CHANGED'

    return True, None
