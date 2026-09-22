"""Runtime Core governado para eventos operacionais do ReqSys.

Este módulo é intencionalmente pequeno e não invasivo: fornece uma fundação
reutilizável para event bus, envelope, retry e dead letter queue sem acoplar o
runtime às APIs existentes. A integração com workflows/agentes deve ocorrer por
incrementos posteriores, preservando contratos públicos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Iterable
from uuid import uuid4


class RuntimeEventStatus(str, Enum):
    """Estados técnicos de processamento de um evento do Runtime Core."""

    PENDING = 'pending'
    DELIVERED = 'delivered'
    FAILED = 'failed'
    DEAD_LETTER = 'dead_letter'


@dataclass(frozen=True)
class RetryPolicy:
    """Política simples de retentativa para handlers síncronos/in-memory."""

    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError('max_attempts deve ser maior ou igual a 1')


@dataclass(frozen=True)
class RuntimeEventEnvelope:
    """Envelope padrão para rastrear eventos de agentes, workflows e integrações."""

    event_type: str
    source: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = 'sem-correlation-id'
    causation_id: str | None = None
    event_id: str = field(default_factory=lambda: f'evt-{uuid4()}')
    schema_version: str = '1.0.0'
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        campos_obrigatorios = {
            'event_type': self.event_type,
            'source': self.source,
            'aggregate_type': self.aggregate_type,
            'aggregate_id': self.aggregate_id,
        }
        faltantes = [campo for campo, valor in campos_obrigatorios.items() if not str(valor or '').strip()]
        if faltantes:
            raise ValueError(f'Campos obrigatorios ausentes no envelope: {", ".join(faltantes)}')

    def to_audit_payload(self) -> dict[str, Any]:
        """Serialização mínima, segura e estável para auditoria/observabilidade."""

        return {
            'schema_version': self.schema_version,
            'event_id': self.event_id,
            'event_type': self.event_type,
            'source': self.source,
            'aggregate_type': self.aggregate_type,
            'aggregate_id': self.aggregate_id,
            'correlation_id': self.correlation_id,
            'causation_id': self.causation_id,
            'occurred_at': self.occurred_at,
            'payload_minimo': self.payload,
        }


@dataclass(frozen=True)
class RuntimeDeliveryResult:
    """Resultado de entrega de um evento para um handler inscrito."""

    event_id: str
    handler_name: str
    status: RuntimeEventStatus
    attempts: int
    error: str | None = None


@dataclass(frozen=True)
class DeadLetterItem:
    """Registro de falha definitiva para reprocessamento governado posterior."""

    envelope: RuntimeEventEnvelope
    handler_name: str
    attempts: int
    error: str
    failed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


RuntimeHandler = Callable[[RuntimeEventEnvelope], None]


class RuntimeEventBus:
    """Event bus governado, síncrono e in-memory para fundação incremental.

    A decisão de iniciar in-memory reduz risco, evita dependência de broker externo
    e permite acoplar posteriormente Redis, Kafka, RabbitMQ, SQL outbox ou fila
    corporativa sem mudar o contrato básico do envelope.
    """

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self._handlers: dict[str, list[RuntimeHandler]] = {}
        self._dead_letters: list[DeadLetterItem] = []
        self._published_events: list[RuntimeEventEnvelope] = []

    def subscribe(self, event_type: str, handler: RuntimeHandler) -> None:
        if not event_type.strip():
            raise ValueError('event_type deve ser informado')
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, envelope: RuntimeEventEnvelope) -> list[RuntimeDeliveryResult]:
        self._published_events.append(envelope)
        handlers = self._handlers.get(envelope.event_type, [])
        if not handlers:
            return [
                RuntimeDeliveryResult(
                    event_id=envelope.event_id,
                    handler_name='sem-handler',
                    status=RuntimeEventStatus.PENDING,
                    attempts=0,
                )
            ]

        return [self._deliver(envelope, handler) for handler in handlers]

    def dead_letters(self) -> tuple[DeadLetterItem, ...]:
        return tuple(self._dead_letters)

    def published_events(self) -> tuple[RuntimeEventEnvelope, ...]:
        return tuple(self._published_events)

    def pending_event_types(self) -> Iterable[str]:
        return tuple(sorted(self._handlers))

    def _deliver(self, envelope: RuntimeEventEnvelope, handler: RuntimeHandler) -> RuntimeDeliveryResult:
        handler_name = getattr(handler, '__name__', handler.__class__.__name__)
        last_error: Exception | None = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                handler(envelope)
                return RuntimeDeliveryResult(
                    event_id=envelope.event_id,
                    handler_name=handler_name,
                    status=RuntimeEventStatus.DELIVERED,
                    attempts=attempt,
                )
            except Exception as exc:  # pragma: no cover - exercitado pelos testes de DLQ
                last_error = exc

        error_message = str(last_error or 'erro desconhecido')
        self._dead_letters.append(
            DeadLetterItem(
                envelope=envelope,
                handler_name=handler_name,
                attempts=self.retry_policy.max_attempts,
                error=error_message,
            )
        )
        return RuntimeDeliveryResult(
            event_id=envelope.event_id,
            handler_name=handler_name,
            status=RuntimeEventStatus.DEAD_LETTER,
            attempts=self.retry_policy.max_attempts,
            error=error_message,
        )
