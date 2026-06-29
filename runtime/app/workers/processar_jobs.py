from __future__ import annotations

import asyncio
import logging

from app.application.services.job_service import JobService
from app.infrastructure.queue.asyncio_queue import AsyncioQueueGateway

logger = logging.getLogger("reqsys.runtime.worker")


async def executar_worker_local(service: JobService, queue: AsyncioQueueGateway) -> None:
    logger.info("worker_local_iniciado")
    while True:
        job_id = await queue.consumir()
        try:
            await service.processar_job(job_id)
        except Exception:  # pragma: no cover - proteção operacional do loop
            logger.exception("erro_nao_tratado_no_worker", extra={"job_id": job_id})
        finally:
            queue.confirmar()
            await asyncio.sleep(0)
