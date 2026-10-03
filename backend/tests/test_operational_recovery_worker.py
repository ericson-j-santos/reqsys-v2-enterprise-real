import pytest

from app.core.operational_queue import OperationalQueue, OperationalQueueUnavailableError
from app.core.operational_recovery_worker import (
    OperationalRecoveryWorker,
    RecoveryWorkerSettings,
    _claimed_messages,
)


def test_claimed_messages_normalizes_redis_response():
    response = ['0-0', [('1700000000000-0', {'task_id': 'task-1'})], []]

    assert _claimed_messages(response) == [
        ('1700000000000-0', {'task_id': 'task-1'}),
    ]


def test_claimed_messages_handles_empty_response():
    assert _claimed_messages(None) == []
    assert _claimed_messages([]) == []
    assert _claimed_messages(['0-0', None]) == []


def test_recovery_settings_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_QUEUE_CLAIM_MIN_IDLE_MS', '120000')
    monkeypatch.setenv('OPERATIONAL_QUEUE_CLAIM_BATCH_SIZE', '25')
    monkeypatch.setenv('OPERATIONAL_QUEUE_RECOVERY_POLL_SECONDS', '2.5')

    settings = RecoveryWorkerSettings.from_environment()

    assert settings.min_idle_ms == 120000
    assert settings.batch_size == 25
    assert settings.poll_interval_seconds == 2.5


def test_recovery_settings_reject_invalid_values(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_QUEUE_CLAIM_BATCH_SIZE', '0')

    with pytest.raises(ValueError, match='maior que zero'):
        RecoveryWorkerSettings.from_environment()


@pytest.mark.asyncio
async def test_recovery_worker_fails_closed_without_redis_streams():
    worker = OperationalRecoveryWorker(
        queue=OperationalQueue(),
        settings=RecoveryWorkerSettings(),
    )

    with pytest.raises(
        OperationalQueueUnavailableError,
        match='OPERATIONAL_QUEUE_PROVIDER=redis_streams',
    ):
        await worker.run_once()
