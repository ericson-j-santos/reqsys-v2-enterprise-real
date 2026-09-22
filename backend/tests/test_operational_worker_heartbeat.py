from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.operational_worker_healthcheck import evaluate_heartbeat
from app.core.operational_worker_heartbeat import (
    OperationalWorkerHeartbeat,
    OperationalWorkerHeartbeatSettings,
)


def _payload(timestamp: datetime, **overrides):
    payload = {
        'schema_version': '1.0.0',
        'component': 'operational_worker_runtime',
        'status': 'running',
        'timestamp': timestamp.isoformat(),
        'consumer_running': True,
        'recovery_running': True,
    }
    payload.update(overrides)
    return payload


def test_evaluate_heartbeat_healthy(tmp_path: Path):
    now = datetime.now(UTC)
    path = tmp_path / 'heartbeat.json'
    path.write_text(json.dumps(_payload(now - timedelta(seconds=2))), encoding='utf-8')

    result = evaluate_heartbeat(path, stale_after_seconds=30, now=now)

    assert result['status'] == 'healthy'
    assert result['age_seconds'] == 2.0


@pytest.mark.parametrize(
    ('overrides', 'message'),
    [
        ({'status': 'stopped'}, 'não está running'),
        ({'consumer_running': False}, 'consumer parado'),
        ({'recovery_running': False}, 'recovery worker parado'),
    ],
)
def test_evaluate_heartbeat_rejects_inactive_components(
    tmp_path: Path,
    overrides,
    message,
):
    now = datetime.now(UTC)
    path = tmp_path / 'heartbeat.json'
    path.write_text(json.dumps(_payload(now, **overrides)), encoding='utf-8')

    with pytest.raises(RuntimeError, match=message):
        evaluate_heartbeat(path, stale_after_seconds=30, now=now)


def test_evaluate_heartbeat_rejects_stale(tmp_path: Path):
    now = datetime.now(UTC)
    path = tmp_path / 'heartbeat.json'
    path.write_text(json.dumps(_payload(now - timedelta(seconds=31))), encoding='utf-8')

    with pytest.raises(RuntimeError, match='heartbeat expirado'):
        evaluate_heartbeat(path, stale_after_seconds=30, now=now)


def test_heartbeat_writes_atomic_snapshot(tmp_path: Path):
    path = tmp_path / 'heartbeat.json'
    heartbeat = OperationalWorkerHeartbeat(
        OperationalWorkerHeartbeatSettings(
            path=path,
            interval_seconds=1,
            stale_after_seconds=3,
        ),
        state_provider=lambda: {
            'consumer_running': True,
            'recovery_running': True,
        },
    )

    heartbeat._write(status='running')
    payload = json.loads(path.read_text(encoding='utf-8'))

    assert payload['status'] == 'running'
    assert payload['consumer_running'] is True
    assert payload['recovery_running'] is True


def test_settings_reject_stale_threshold_not_greater_than_interval(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_WORKER_HEARTBEAT_INTERVAL_SECONDS', '10')
    monkeypatch.setenv('OPERATIONAL_WORKER_HEARTBEAT_STALE_AFTER_SECONDS', '10')

    with pytest.raises(ValueError, match='deve ser maior que o intervalo'):
        OperationalWorkerHeartbeatSettings.from_environment()
