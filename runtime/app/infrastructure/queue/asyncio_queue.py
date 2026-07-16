from __future__ import annotations

import asyncio


class AsyncioQueueGateway:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def publicar(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def consumir(self) -> str:
        return await self._queue.get()

    async def confirmar(self) -> None:
        self._queue.task_done()

    async def tamanho(self) -> int:
        return self._queue.qsize()

    async def ping(self) -> bool:
        return True

    async def fechar(self) -> None:
        return None
