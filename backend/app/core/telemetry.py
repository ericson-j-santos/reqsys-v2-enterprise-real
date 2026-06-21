import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.correlation import obter_correlation_id

logger = logging.getLogger("reqsys.telemetry")


def log_evento(evento: str, **campos: Any) -> None:
    logger.info({"event": evento, "correlation_id": obter_correlation_id(), **campos})


def log_erro(evento: str, erro: Exception | str, **campos: Any) -> None:
    logger.error({"event": evento, "correlation_id": obter_correlation_id(), "error": str(erro), **campos})


@contextmanager
def medir_operacao(nome: str, **campos: Any) -> Iterator[None]:
    inicio = time.perf_counter()
    log_evento(f"{nome}.started", **campos)
    try:
        yield
        log_evento(f"{nome}.completed", duration_ms=int((time.perf_counter() - inicio) * 1000), **campos)
    except Exception as exc:
        log_erro(f"{nome}.failed", exc, duration_ms=int((time.perf_counter() - inicio) * 1000), **campos)
        raise
