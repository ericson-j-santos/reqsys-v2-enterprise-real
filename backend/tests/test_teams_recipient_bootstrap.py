import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.teams_notification_recipient import TeamsNotificationRecipient
from app.services.teams_recipient_bootstrap import (
    load_recipient_config,
    normalize_recipients,
    reconcile_recipients,
)


def _document(*, name='Aprovador inicial', priority=10):
    return {
        'schema_version': '1.0.0',
        'policies': [
            {
                'name': 'hitl-approvers',
                'delivery_mode': 'all',
                'recipients': [
                    {
                        'name': name,
                        'destination_id': 'approver@example.com',
                        'destination_type': 'chat',
                        'priority': priority,
                        'active': True,
                        'notes': 'bootstrap de teste',
                    }
                ],
            }
        ],
    }


def _runtime_document():
    return {
        'schema_version': '1.1.0',
        'policies': [
            {
                'name': 'hitl-approvers',
                'delivery_mode': 'all',
                'recipient_source': 'runtime_db',
                'recipients': [],
            }
        ],
    }


def test_load_and_normalize_recipient_config(tmp_path):
    path = tmp_path / 'recipients.json'
    path.write_text(json.dumps(_document()), encoding='utf-8')

    recipients = normalize_recipients(load_recipient_config(path))

    assert recipients == [
        {
            'politica': 'hitl-approvers',
            'nome': 'Aprovador inicial',
            'destino_id': 'approver@example.com',
            'destino_tipo': 'chat',
            'prioridade': 10,
            'ativo': True,
            'observacao': 'bootstrap de teste',
        }
    ]


def test_runtime_managed_policy_does_not_seed_or_delete_recipients(tmp_path):
    path = tmp_path / 'recipients.json'
    path.write_text(json.dumps(_runtime_document()), encoding='utf-8')

    recipients = normalize_recipients(load_recipient_config(path))

    assert recipients == []


def test_runtime_managed_policy_rejects_inline_identity():
    document = _runtime_document()
    document['policies'][0]['recipients'].append(
        {
            'name': 'Nao versionar',
            'destination_id': 'person@example.com',
            'destination_type': 'chat',
        }
    )

    with pytest.raises(ValueError, match='nao pode versionar destinatarios'):
        normalize_recipients(document)


def test_reconcile_is_idempotent_and_updates_existing_record():
    test_engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=test_engine)

    with Session(test_engine) as db:
        first = reconcile_recipients(db, normalize_recipients(_document()))
        second = reconcile_recipients(db, normalize_recipients(_document()))
        third = reconcile_recipients(
            db,
            normalize_recipients(_document(name='Aprovador atualizado', priority=5)),
        )
        records = list(db.execute(select(TeamsNotificationRecipient)).scalars())

    assert first == {'configured': 1, 'created': 1, 'updated': 0, 'unchanged': 0}
    assert second == {'configured': 1, 'created': 0, 'updated': 0, 'unchanged': 1}
    assert third == {'configured': 1, 'created': 0, 'updated': 1, 'unchanged': 0}
    assert len(records) == 1
    assert records[0].nome == 'Aprovador atualizado'
    assert records[0].prioridade == 5


def test_normalize_rejects_duplicate_or_invalid_destination_type():
    duplicate = _document()
    duplicate['policies'][0]['recipients'].append(dict(duplicate['policies'][0]['recipients'][0]))
    with pytest.raises(ValueError, match='duplicado'):
        normalize_recipients(duplicate)

    invalid = _document()
    invalid['policies'][0]['recipients'][0]['destination_type'] = 'unsupported'
    with pytest.raises(ValueError, match='destination_type invalido'):
        normalize_recipients(invalid)
