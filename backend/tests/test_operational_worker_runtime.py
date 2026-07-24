import asyncio

import pytest

from app.core.operational_worker_runtime import (
    OperationalWorkerRuntime,
    OperationalWorkerRuntimeSettings,
)


class StubWorker:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class StubRecoveryWorker(StubWorker):
    def _validate_provider(self):
        return self


@pytest.mark.asyncio
async def test_runtime_starts_and_stops_both_workers():
    worker = StubWorker()
    recovery = StubRecoveryWorker()
    runtime = OperationalWorkerRuntime(
        worker=worker,
        recovery_worker=recovery,
        settings=OperationalWorkerRuntimeSettings(shutdown_timeout_seconds=1),
    )

    task = asyncio.create_task(runtime.run())
    await asyncio.sleep(0)

    assert worker.started is True
    assert recovery.started is True

    runtime.request_stop()
    await task

    assert worker.stopped is True
    assert recovery.stopped is True


def test_runtime_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_WORKER_SHUTDOWN_TIMEOUT_SECONDS', '7.5')

    settings = OperationalWorkerRuntimeSettings.from_environment()

    assert settings.shutdown_timeout_seconds == 7.5


def test_runtime_settings_reject_non_positive_value(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_WORKER_SHUTDOWN_TIMEOUT_SECONDS', '0')

    with pytest.raises(ValueError, match='maior que zero'):
        OperationalWorkerRuntimeSettings.from_environment()
