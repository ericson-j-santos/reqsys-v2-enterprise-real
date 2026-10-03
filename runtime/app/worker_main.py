from __future__ import annotations

import asyncio
import logging

from app.core.components import build_runtime_components
from app.core.config import get_settings
from app.workers.processar_jobs import executar_worker_local

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reqsys.runtime.worker.main")


async def main() -> None:
    settings = get_settings()
    if settings.queue_backend != "redis" or settings.storage_backend != "redis":
        raise RuntimeError("O worker independente exige QUEUE_BACKEND=redis e STORAGE_BACKEND=redis")

    components = build_runtime_components(settings)
    logger.info(
        "worker_independente_iniciado",
        extra={"queue_backend": settings.queue_backend, "storage_backend": settings.storage_backend},
    )
    try:
        await executar_worker_local(components.service, components.queue)
    finally:
        await components.queue.fechar()


if __name__ == "__main__":
    asyncio.run(main())
