from __future__ import annotations

import asyncio

import pytest

from app.workers.processar_jobs import executar_worker_local


class QueueProbe:
    def __init__(self) -> None:
        self.recovery_called = False
        self.consume_called = False

    async def recuperar_jobs_orfaos(self) -> int:
        self.recovery_called = True
        return 2

    async def consumir(self) -> str:
        self.consume_called = True
        raise asyncio.CancelledError

    async def confirmar(self) -> None:
        return None


class ServiceProbe:
    async def processar_job(self, job_id: str) -> None:
        raise AssertionError(f"job inesperado: {job_id}")


@pytest.mark.asyncio
async def test_worker_recupera_jobs_antes_de_iniciar_consumo() -> None:
    queue = QueueProbe()

    with pytest.raises(asyncio.CancelledError):
        await executar_worker_local(ServiceProbe(), queue)  # type: ignore[arg-type]

    assert queue.recovery_called is True
    assert queue.consume_called is True
