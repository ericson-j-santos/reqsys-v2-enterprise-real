from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass

from app.core.operational_queue import OperationalQueueUnavailableError
from app.core.operational_recovery_worker import OperationalRecoveryWorker
from app.core.operational_worker import OperationalWorker
from app.core.operational_worker_heartbeat import OperationalWorkerHeartbeat

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
    """Executa consumo, recuperação e heartbeat no mesmo processo dedicado."""

    def __init__(
        self,
        worker: OperationalWorker | None = None,
        recovery_worker: OperationalRecoveryWorker | None = None,
        heartbeat: OperationalWorkerHeartbeat | None = None,
        settings: OperationalWorkerRuntimeSettings | None = None,
    ) -> None:
        self.worker = worker or OperationalWorker()
        self.recovery_worker = recovery_worker or OperationalRecoveryWorker()
        self.settings = settings or OperationalWorkerRuntimeSettings.from_environment()
        self.heartbeat = heartbeat or OperationalWorkerHeartbeat(
            state_provider=self._heartbeat_state
        )
        self._stop_event = asyncio.Event()

    @staticmethod
    def _component_running(component: object) -> bool:
        """Lê o estado sem acoplar o runtime a uma implementação concreta.

        Adaptadores e doubles de teste podem expor ``running`` ou ``started``.
        Em caso de contrato incompleto, o estado permanece fail-closed.
        """

        running = getattr(component, 'running', None)
        if running is not None:
            return bool(running)
        return bool(getattr(component, 'started', False))

    def _heartbeat_state(self) -> dict[str, bool]:
        return {
            'consumer_running': self._component_running(self.worker),
            'recovery_running': self._component_running(self.recovery_worker),
        }

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        self.recovery_worker._validate_provider()
        self.worker.start()
        self.recovery_worker.start()
        self.heartbeat.start()
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
            self.heartbeat.stop(),
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
