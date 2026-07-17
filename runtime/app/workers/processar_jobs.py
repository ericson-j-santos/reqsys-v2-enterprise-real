from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from app.application.services.job_service import JobService
from app.core.async_compat import resolve_maybe_awaitable

logger = logging.getLogger("reqsys.runtime.worker")


async def _renovar_lease_periodicamente(queue: Any) -> None:
    renovar = getattr(queue, "renovar_lease", None)
    if renovar is None:
        return
    intervalo_segundos = getattr(queue, "lease_renew_interval_seconds", 20)
    while True:
        await asyncio.sleep(intervalo_segundos)
        renovado = await resolve_maybe_awaitable(renovar())
        if not renovado:
            logger.warning("lease_nao_renovado", extra={"intervalo_segundos": intervalo_segundos})
            return


async def executar_worker_local(service: JobService, queue: Any) -> None:
    recuperar = getattr(queue, "recuperar_jobs_orfaos", None)
    if recuperar is not None:
        recuperados = await resolve_maybe_awaitable(recuperar())
        logger.info("jobs_orfaos_recuperados", extra={"quantidade": recuperados})

    logger.info("worker_iniciado")
    while True:
        job_id = await queue.consumir()
        lease_task = asyncio.create_task(_renovar_lease_periodicamente(queue))
        try:
            await service.processar_job(job_id)
        except Exception:  # pragma: no cover - proteção operacional do loop
            logger.exception("erro_nao_tratado_no_worker", extra={"job_id": job_id})
        finally:
            lease_task.cancel()
            with suppress(asyncio.CancelledError):
                await lease_task
            await resolve_maybe_awaitable(queue.confirmar())
            await asyncio.sleep(0)
