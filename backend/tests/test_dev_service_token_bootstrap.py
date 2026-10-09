from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core import dev_service_token_bootstrap as bootstrap
from app.models.auditoria import AuditoriaEvento
from app.models.service_token import ServiceToken


class FakeQuery:
    def __init__(self, records):
        self.records = records

    def filter(self, *_args):
        return self

    def all(self):
        return self.records


class FakeDb:
    def __init__(self, records=None):
        self.records = records or []
        self.added = []
        self.committed = False

    def query(self, _model):
        return FakeQuery(self.records)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        for value in self.added:
            if isinstance(value, ServiceToken):
                value.id = 41

    def commit(self):
        self.committed = True


def test_rotates_allowlisted_identity_and_audits(monkeypatch):
    monkeypatch.setattr(bootstrap, 'settings', SimpleNamespace(normalized_environment='desenvolvimento'))
    previous = ServiceToken(label='pc24x7-teams-dev', token_hash='a' * 64, scopes='[]')
    db = FakeDb([previous])

    raw = bootstrap.rotate_dev_service_token(
        db,
        label='pc24x7-teams-dev',
        scope='teams_gateway:ai_conversations',
    )

    assert len(raw) > 20
    assert previous.revoked_at is not None
    created = next(value for value in db.added if isinstance(value, ServiceToken))
    assert created.token_hash != raw
    assert json.loads(created.scopes) == ['teams_gateway:ai_conversations']
    event = next(value for value in db.added if isinstance(value, AuditoriaEvento))
    assert event.usuario == bootstrap.ACTOR
    assert event.acao == 'SERVICE_TOKEN_ROTACIONADO_LOCAL_DEV'
    assert db.committed is True


def test_rotates_report_builder_dev_identity(monkeypatch):
    monkeypatch.setattr(bootstrap, 'settings', SimpleNamespace(normalized_environment='desenvolvimento'))
    db = FakeDb()

    raw = bootstrap.rotate_dev_service_token(
        db,
        label='report-builder-email-dev',
        scope='report_builder:send',
    )

    assert len(raw) > 20
    created = next(value for value in db.added if isinstance(value, ServiceToken))
    assert created.label == 'report-builder-email-dev'
    assert json.loads(created.scopes) == ['report_builder:send']
    assert db.committed is True


@pytest.mark.parametrize('environment', ['production', 'staging', 'testes'])
def test_blocks_outside_development(monkeypatch, environment):
    monkeypatch.setattr(bootstrap, 'settings', SimpleNamespace(normalized_environment=environment))
    with pytest.raises(bootstrap.LocalBootstrapBlocked, match='environment_not_development'):
        bootstrap.rotate_dev_service_token(
            FakeDb(),
            label='pc24x7-teams-dev',
            scope='teams_gateway:ai_conversations',
        )


def test_blocks_unapproved_identity(monkeypatch):
    monkeypatch.setattr(bootstrap, 'settings', SimpleNamespace(normalized_environment='desenvolvimento'))
    with pytest.raises(bootstrap.LocalBootstrapBlocked, match='service_identity_not_allowed'):
        bootstrap.rotate_dev_service_token(FakeDb(), label='arbitrary', scope='*')
