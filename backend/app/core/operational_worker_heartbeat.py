# ruff: noqa: I001
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

HEARTBEAT_FILENAME = 'reqsys-operational-worker-heartbeat.json'


def _default_heartbeat_path() -> Path:
    return Path(tempfile.gettempdir()) / HEARTBEAT_FILENAME


@dataclass(frozen=True, slots=True)
class OperationalWorkerHeartbeatSettings:
    path: Path = field(default_factory=_default_heartbeat_path)
    interval_seconds: float = 10.0
    stale_after_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> 'OperationalWorkerHeartbeatSettings':
        path = Path(
            os.getenv(
                'OPERATIONAL_WORKER_HEARTBEAT_PATH',
                str(_default_heartbeat_path()),
            ).strip()
        )
        interval = _positive_float('OPERATIONAL_WORKER_HEARTBEAT_INTERVAL_SECONDS', 10.0)
        stale_after = _positive_float('OPERATIONAL_WORKER_HEARTBEAT_STALE_AFTER_SECONDS', 30.0)
        if stale_after <= interval:
            raise ValueError(
                'OPERATIONAL_WORKER_HEARTBEAT_STALE_AFTER_SECONDS deve ser maior que o intervalo'
            )
        return cls(path=path, interval_seconds=interval, stale_after_seconds=stale_after)


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f'{name} deve ser numérico positivo') from exc
    if value <= 0:
        raise ValueError(f'{name} deve ser maior que zero')
    return value


class OperationalWorkerHeartbeat:
    def __init__(
        self,
        settings: OperationalWorkerHeartbeatSettings | None = None,
        state_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings or OperationalWorkerHeartbeatSettings.from_environment()
        self.state_provider = state_provider or (lambda: {})
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name='reqsys-operational-worker-heartbeat')

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._write(status='stopped')

    async def _run(self) -> None:
        while self._running:
            self._write(status='running')
            await asyncio.sleep(self.settings.interval_seconds)

    def _write(self, *, status: str) -> None:
        payload = {
            'schema_version': '1.0.0',
            'component': 'operational_worker_runtime',
            'status': status,
            'timestamp': datetime.now(UTC).isoformat(),
            **self.state_provider(),
        }
        self.settings.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=self.settings.path.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            temporary_path = Path(handle.name)
        temporary_path.replace(self.settings.path)
