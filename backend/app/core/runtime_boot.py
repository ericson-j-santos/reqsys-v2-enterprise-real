"""Utilitários de boot resiliente para runtime público Fly.io."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine

logger = logging.getLogger('reqsys.boot')

_DEFAULT_MAX_ATTEMPTS = 5
_DEFAULT_DELAY_SECONDS = 1.0


def probe_database(*, max_attempts: int = _DEFAULT_MAX_ATTEMPTS, delay_seconds: float = _DEFAULT_DELAY_SECONDS) -> tuple[bool, str]:
    """Verifica conectividade do banco com retries curtos no startup."""
    last_error = 'unknown'
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
            if attempt > 1:
                logger.info('database_ready after_attempt=%s', attempt)
            return True, 'ok'
        except SQLAlchemyError as exc:
            last_error = type(exc).__name__
            logger.warning('database_probe_failed attempt=%s error=%s', attempt, last_error)
            if attempt < max_attempts:
                time.sleep(delay_seconds)
    return False, last_error


def build_health_payload(*, database_ok: bool, database_detail: str) -> dict[str, Any]:
    status = 'ok' if database_ok else 'degraded'
    return {
        'status': status,
        'service': 'reqsys-api',
        'database': {
            'status': 'ok' if database_ok else 'unavailable',
            'detail': database_detail,
        },
    }
