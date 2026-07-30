from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.models.teams_notification_recipient import TeamsNotificationRecipient

logger = logging.getLogger('reqsys.teams_recipient_bootstrap')

_ALLOWED_DESTINATION_TYPES = {'auto', 'chat', 'chat_1a1', 'canal', 'webhook'}


def load_recipient_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    document = json.loads(config_path.read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('A configuracao de destinatarios deve ser um objeto JSON.')
    if document.get('schema_version') != '1.0.0':
        raise ValueError('schema_version de destinatarios nao suportada.')
    if not isinstance(document.get('policies'), list):
        raise ValueError('policies deve ser uma lista.')
    return document


def normalize_recipients(document: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for policy in document['policies']:
        if not isinstance(policy, dict):
            raise ValueError('Cada politica deve ser um objeto.')
        policy_name = str(policy.get('name') or '').strip().lower()
        if not policy_name:
            raise ValueError('Politica sem name.')
        recipients = policy.get('recipients')
        if not isinstance(recipients, list):
            raise ValueError(f'recipients deve ser uma lista na politica {policy_name}.')

        for index, recipient in enumerate(recipients, start=1):
            if not isinstance(recipient, dict):
                raise ValueError(f'Destinatario invalido na politica {policy_name}.')
            destination_id = str(recipient.get('destination_id') or '').strip()
            destination_type = str(recipient.get('destination_type') or 'chat').strip().lower()
            if not destination_id:
                raise ValueError(f'Destinatario {index} sem destination_id na politica {policy_name}.')
            if destination_type not in _ALLOWED_DESTINATION_TYPES:
                raise ValueError(
                    f'destination_type invalido na politica {policy_name}: {destination_type}.'
                )
            key = (policy_name, destination_type, destination_id.casefold())
            if key in seen:
                raise ValueError(f'Destinatario duplicado na politica {policy_name}.')
            seen.add(key)
            normalized.append(
                {
                    'politica': policy_name,
                    'nome': str(recipient.get('name') or '').strip(),
                    'destino_id': destination_id,
                    'destino_tipo': destination_type,
                    'prioridade': int(recipient.get('priority', 100)),
                    'ativo': bool(recipient.get('active', True)),
                    'observacao': str(recipient.get('notes') or '').strip(),
                }
            )

    return normalized


def reconcile_recipients(db: Session, recipients: list[dict[str, Any]]) -> dict[str, int]:
    created = 0
    updated = 0
    unchanged = 0

    for values in recipients:
        existing = db.execute(
            select(TeamsNotificationRecipient).where(
                TeamsNotificationRecipient.politica == values['politica'],
                TeamsNotificationRecipient.destino_tipo == values['destino_tipo'],
                TeamsNotificationRecipient.destino_id == values['destino_id'],
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(TeamsNotificationRecipient(**values))
            created += 1
            continue

        changed = False
        for field in ('nome', 'prioridade', 'ativo', 'observacao'):
            if getattr(existing, field) != values[field]:
                setattr(existing, field, values[field])
                changed = True
        if changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return {'configured': len(recipients), 'created': created, 'updated': updated, 'unchanged': unchanged}


def bootstrap_recipients(path: str | Path) -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    document = load_recipient_config(path)
    recipients = normalize_recipients(document)
    with SessionLocal() as db:
        result = reconcile_recipients(db, recipients)
    logger.info(
        'teams_recipient_bootstrap_ok configured=%s created=%s updated=%s unchanged=%s',
        result['configured'],
        result['created'],
        result['updated'],
        result['unchanged'],
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Bootstrap governado de destinatarios Teams.')
    parser.add_argument('--config', required=True, help='Arquivo JSON de politicas e destinatarios.')
    args = parser.parse_args()
    result = bootstrap_recipients(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
