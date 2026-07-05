"""Retry com backoff e circuit breaker compartilhados para adapters externos (ADR-010)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Callable, TypeVar

from app.core.telemetry import log_erro, log_evento

T = TypeVar('T')


class CircuitBreakerOpenError(RuntimeError):
    """Levantado quando o circuito esta aberto e a chamada e bloqueada antes de atingir o adapter externo."""


@dataclass
class CircuitBreaker:
    """Circuit breaker simples baseado em contagem de falhas consecutivas + cooldown."""

    name: str
    failure_threshold: int = 3
    cooldown_seconds: int = 60
    failures: int = field(default=0, init=False)
    opened_at: datetime | None = field(default=None, init=False)

    def is_open(self, *, now: datetime | None = None) -> bool:
        if self.opened_at is None:
            return False
        now = now or datetime.now(UTC)
        return now - self.opened_at < timedelta(seconds=self.cooldown_seconds)

    def guard(self) -> None:
        if self.is_open():
            raise CircuitBreakerOpenError(
                f"Circuito '{self.name}' aberto apos falhas consecutivas; aguardando cooldown antes de nova tentativa."
            )

    def record_success(self) -> None:
        if self.failures or self.opened_at:
            log_evento('circuit_breaker.closed', circuito=self.name)
        self.failures = 0
        self.opened_at = None

    def record_failure(self, *, now: datetime | None = None) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold and self.opened_at is None:
            self.opened_at = now or datetime.now(UTC)
            log_erro('circuit_breaker.opened', f'{self.failures} falhas consecutivas', circuito=self.name)

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = None


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    circuit: CircuitBreaker | None = None,
) -> T:
    """Executa `fn` com retry exponencial e, opcionalmente, um circuit breaker compartilhado.

    O timeout da chamada externa e responsabilidade do proprio `fn` (ex.: passar
    `timeout=` no cliente HTTP); aqui tratamos apenas retry + circuito, conforme ADR-010.
    """
    if circuit is not None:
        circuit.guard()

    last_error: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = fn()
        except retry_on as exc:
            last_error = exc
            if attempt < max_retries:
                sleep(backoff_seconds * (2 ** (attempt - 1)))
            continue

        if circuit is not None:
            circuit.record_success()
        return result

    assert last_error is not None
    if circuit is not None:
        circuit.record_failure()
    raise last_error
