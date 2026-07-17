from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.application.services.job_service import JobService
from app.core.async_compat import resolve_maybe_awaitable

logger = logging.getLogger("reqsys.runtime.worker")


async def executar_worker_local(service: JobService, queue: Any) -> None:
    recuperar = getattr(queue, "recuperar_jobs_orfaos", None)
    if recuperar is not None:
        recuperados = await resolve_maybe_awaitable(recuperar())
        logger.info("jobs_orfaos_recuperados", extra={"quantidade": recuperados})

    logger.info("worker_iniciado")
    while True:
        job_id = await queue.consumir()
        try:
            await service.processar_job(job_id)
        except Exception:  # pragma: no cover - proteção operacional do loop
            logger.exception("erro_nao_tratado_no_worker", extra={"job_id": job_id})
        finally:
            await resolve_maybe_awaitable(queue.confirmar())
            await asyncio.sleep(0)
