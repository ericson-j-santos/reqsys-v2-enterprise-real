"""Caminhos críticos — runtime boot e health payload."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

import app.core.runtime_boot as module
from app.core.runtime_boot import build_health_payload, probe_database


def test_build_health_payload_degraded_quando_banco_indisponivel():
    payload = build_health_payload(database_ok=False, database_detail='timeout')
    assert payload['status'] == 'degraded'
    assert payload['database']['status'] == 'unavailable'


def test_probe_database_retenta_ate_esgotar(monkeypatch):
    calls = {'count': 0}

    class _BrokenConnection:
        def __enter__(self):
            calls['count'] += 1
            raise SQLAlchemyError('db down')

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(module.engine, 'connect', lambda: _BrokenConnection())
    monkeypatch.setattr(module.time, 'sleep', lambda _seconds: None)
    ok, detail = probe_database(max_attempts=2, delay_seconds=0)
    assert ok is False
    assert detail == 'SQLAlchemyError'
    assert calls['count'] == 2


def test_probe_database_sucesso_na_segunda_tentativa(monkeypatch):
    calls = {'count': 0}

    class _Connection:
        def __enter__(self):
            calls['count'] += 1
            if calls['count'] == 1:
                raise SQLAlchemyError('transient')
            return self

        def __exit__(self, *args):
            return False

        def execute(self, _statement):
            return None

    monkeypatch.setattr(module.engine, 'connect', lambda: _Connection())
    monkeypatch.setattr(module.time, 'sleep', lambda _seconds: None)
    ok, detail = probe_database(max_attempts=2, delay_seconds=0)
    assert ok is True
    assert detail == 'ok'
