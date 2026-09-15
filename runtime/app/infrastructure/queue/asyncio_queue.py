from __future__ import annotations

import asyncio

from app.infrastructure.queue.errors import QueueCapacityError


class AsyncioQueueGateway:
    def __init__(self, max_queue_size: int = 1000) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue_size)
        self._max_queue_size = max_queue_size
        self._delayed_tasks: set[asyncio.Task[None]] = set()
        self._dlq: list[str] = []

    def _sem_capacidade(self) -> bool:
        return self._queue.qsize() + len(self._delayed_tasks) >= self._max_queue_size

    async def publicar(self, job_id: str, *, delay_seconds: float = 0) -> None:
        if self._sem_capacidade():
            raise QueueCapacityError("queue_capacity_exceeded")

        if delay_seconds <= 0:
            await self._queue.put(job_id)
            return

        async def publicar_depois() -> None:
            await asyncio.sleep(delay_seconds)
            await self._queue.put(job_id)

        task = asyncio.create_task(publicar_depois())
        self._delayed_tasks.add(task)
        task.add_done_callback(self._delayed_tasks.discard)

    async def consumir(self) -> str:
        return await self._queue.get()

    def confirmar(self) -> None:
        self._queue.task_done()

    async def quarentenar(self, job_id: str) -> None:
        if job_id not in self._dlq:
            self._dlq.append(job_id)

    def tamanho_dlq(self) -> int:
        return len(self._dlq)

    def tamanho(self) -> int:
        return self._queue.qsize() + len(self._delayed_tasks)

    async def ping(self) -> bool:
        return True

    async def fechar(self) -> None:
        for task in list(self._delayed_tasks):
            task.cancel()
        if self._delayed_tasks:
            await asyncio.gather(*self._delayed_tasks, return_exceptions=True)
        self._delayed_tasks.clear()
