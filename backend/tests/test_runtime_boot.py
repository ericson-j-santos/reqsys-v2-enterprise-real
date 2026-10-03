"""Testes de boot resiliente do runtime público."""

from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from app.core.runtime_boot import build_health_payload, probe_database


def test_probe_database_succeeds_with_sqlite():
    ok, detail = probe_database(max_attempts=1, delay_seconds=0)
    assert ok is True
    assert detail == 'ok'


def test_build_health_payload_ok():
    payload = build_health_payload(database_ok=True, database_detail='ok')
    assert payload['status'] == 'ok'
    assert payload['database']['status'] == 'ok'


def test_build_health_payload_degraded():
    payload = build_health_payload(database_ok=False, database_detail='OperationalError')
    assert payload['status'] == 'degraded'
    assert payload['database']['status'] == 'unavailable'


def test_probe_database_retries_until_success():
    with patch('app.core.runtime_boot.engine.connect') as connect_mock:
        connect_mock.side_effect = [
            OperationalError('temporary', {}, Exception('temporary')),
            OperationalError('temporary', {}, Exception('temporary')),
            _fake_connection(),
        ]
        ok, detail = probe_database(max_attempts=3, delay_seconds=0)
        assert ok is True
        assert detail == 'ok'
        assert connect_mock.call_count == 3


class _fake_connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *_args, **_kwargs):
        return None
