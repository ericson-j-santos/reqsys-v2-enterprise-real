from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass

from app.core.operational_queue import OperationalQueueUnavailableError
from app.core.operational_recovery_worker import OperationalRecoveryWorker
from app.core.operational_worker import OperationalWorker

logger = logging.getLogger('reqsys.operational_worker_runtime')


@dataclass(frozen=True, slots=True)
class OperationalWorkerRuntimeSettings:
    shutdown_timeout_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> 'OperationalWorkerRuntimeSettings':
        raw = os.getenv('OPERATIONAL_WORKER_SHUTDOWN_TIMEOUT_SECONDS', '15').strip()
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError(
                'OPERATIONAL_WORKER_SHUTDOWN_TIMEOUT_SECONDS deve ser numérico positivo'
            ) from exc
        if value <= 0:
            raise ValueError(
                'OPERATIONAL_WORKER_SHUTDOWN_TIMEOUT_SECONDS deve ser maior que zero'
            )
        return cls(shutdown_timeout_seconds=value)


class OperationalWorkerRuntime:
    """Executa consumo normal e recuperação de mensagens no mesmo processo dedicado."""

    def __init__(
        self,
        worker: OperationalWorker | None = None,
        recovery_worker: OperationalRecoveryWorker | None = None,
        settings: OperationalWorkerRuntimeSettings | None = None,
    ) -> None:
        self.worker = worker or OperationalWorker()
        self.recovery_worker = recovery_worker or OperationalRecoveryWorker()
        self.settings = settings or OperationalWorkerRuntimeSettings.from_environment()
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        self.recovery_worker._validate_provider()
        self.worker.start()
        self.recovery_worker.start()
        logger.info('operational_worker_runtime_started')

        try:
            await self._stop_event.wait()
        finally:
            await asyncio.wait_for(
                self._stop_components(),
                timeout=self.settings.shutdown_timeout_seconds,
            )
            logger.info('operational_worker_runtime_stopped')

    async def _stop_components(self) -> None:
        await asyncio.gather(
            self.worker.stop(),
            self.recovery_worker.stop(),
        )


async def _main() -> None:
    runtime = OperationalWorkerRuntime()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, runtime.request_stop)
        except NotImplementedError:  # pragma: no cover - Windows
            pass

    try:
        await runtime.run()
    except OperationalQueueUnavailableError:
        logger.exception('operational_worker_runtime_provider_unavailable')
        raise


if __name__ == '__main__':
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
    asyncio.run(_main())
