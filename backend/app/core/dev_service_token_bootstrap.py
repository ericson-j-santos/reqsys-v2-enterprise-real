"""Bootstrap local e restrito de tokens S2S para o runtime PC24x7 DEV.

Este modulo nao expoe endpoint HTTP e recusa qualquer ambiente que nao seja
desenvolvimento. Ele existe para que o supervisor local possa recuperar a
credencial de automacao sem depender de uma sessao administrativa humana.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.service_tokens import hash_token
from app.db import SessionLocal
from app.models.auditoria import AuditoriaEvento
from app.models.service_token import ServiceToken

ALLOWED_IDENTITIES = {
    ('pc24x7-teams-dev', 'teams_gateway:ai_conversations'),
    ('cofre-runtime-evidence-dev', 'cofre:runtime_evidence'),
}
ACTOR = 'machine:pc24x7-dev-supervisor'
CORRELATION_ID = 'pc24x7-token-bootstrap-local'


class LocalBootstrapBlocked(RuntimeError):
    pass


def rotate_dev_service_token(
    db: Session,
    *,
    label: str,
    scope: str,
    expires_in_days: int = 90,
) -> str:
    """Cria um token e revoga os anteriores da mesma identidade numa transacao."""
    if settings.normalized_environment != 'desenvolvimento':
        raise LocalBootstrapBlocked('environment_not_development')
    if (label, scope) not in ALLOWED_IDENTITIES:
        raise LocalBootstrapBlocked('service_identity_not_allowed')
    if expires_in_days < 1 or expires_in_days > 90:
        raise LocalBootstrapBlocked('expires_in_days_out_of_range')

    now = datetime.now(timezone.utc)
    raw_token = token_urlsafe(32)
    current = (
        db.query(ServiceToken)
        .filter(ServiceToken.label == label, ServiceToken.revoked_at.is_(None))
        .all()
    )
    for token in current:
        token.revoked_at = now

    record = ServiceToken(
        label=label,
        token_hash=hash_token(raw_token),
        scopes=json.dumps([scope]),
        expires_at=now + timedelta(days=expires_in_days),
    )
    db.add(record)
    db.flush()
    db.add(AuditoriaEvento(
        correlation_id=CORRELATION_ID,
        usuario=ACTOR,
        acao='SERVICE_TOKEN_ROTACIONADO_LOCAL_DEV',
        entidade='service_token',
        entidade_id=str(record.id),
        payload_minimo=json.dumps({
            'label': label,
            'scopes': [scope],
            'revoked_previous_count': len(current),
            'expires_in_days': expires_in_days,
        }),
    ))
    db.commit()
    return raw_token


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--expires-in-days', type=int, default=90)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        credential = rotate_dev_service_token(
            db,
            label=args.label,
            scope=args.scope,
            expires_in_days=args.expires_in_days,
        )
    except LocalBootstrapBlocked as exc:
        db.rollback()
        print(f'blocked:{exc}')
        return 4
    except SQLAlchemyError:
        db.rollback()
        print('blocked:local_bootstrap_failed')
        return 4
    finally:
        db.close()

    # Unica saida sensivel; o chamador captura o pipe e grava imediatamente no Key Vault.
    sys.stdout.write(credential + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
