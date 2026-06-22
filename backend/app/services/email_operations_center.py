"""Email Operations Center.

Nucleo operacional para gerenciamento governado de envios de e-mail.

Este modulo nao envia e-mails diretamente. Ele organiza a operacao para que
adapters reais, como Gmail API, Microsoft Graph ou SMTP, possam ser plugados
com rastreabilidade, retry, DLQ, replay e metricas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol
from uuid import uuid4


class EmailOperationStatus(StrEnum):
    """Estados canonicos de uma operacao de envio."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    DEAD_LETTER = "DEAD_LETTER"
    FAILED = "FAILED"
    REPLAYED = "REPLAYED"


class EmailOperationSeverity(StrEnum):
    """Semaforo executivo de severidade operacional."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class EmailDeliveryRequest:
    """Solicitacao governada de envio."""

    subject: str
    recipients: tuple[str, ...]
    correlation_id: str
    html_body: str
    text_body: str
    max_attempts: int = 3
    metadata: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.subject.strip():
            raise ValueError("subject is required")
        if not self.recipients:
            raise ValueError("at least one recipient is required")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id is required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than zero")


@dataclass(frozen=True)
class EmailDeliveryResult:
    """Resultado retornado por um adapter de entrega."""

    success: bool
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None


class EmailDeliveryGateway(Protocol):
    """Contrato para adapters reais ou fake de entrega."""

    def send(self, request: EmailDeliveryRequest) -> EmailDeliveryResult:
        """Executa entrega da mensagem."""


@dataclass(frozen=True)
class EmailOperationEvent:
    """Evento da timeline operacional."""

    event_id: str
    operation_id: str
    status: EmailOperationStatus
    severity: EmailOperationSeverity
    correlation_id: str
    message: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class EmailOperation:
    """Registro operacional de envio."""

    operation_id: str
    request: EmailDeliveryRequest
    status: EmailOperationStatus
    attempts: int = 0
    provider_message_id: str | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class EmailOperationsMetrics:
    """Metricas consolidadas do centro operacional."""

    queued: int
    processing: int
    sent: int
    retry_scheduled: int
    dead_letter: int
    failed: int
    replayed: int

    @property
    def total(self) -> int:
        return (
            self.queued
            + self.processing
            + self.sent
            + self.retry_scheduled
            + self.dead_letter
            + self.failed
            + self.replayed
        )


class InMemoryEmailOperationsRepository:
    """Repositorio em memoria para testes, demos e primeira versao operacional."""

    def __init__(self) -> None:
        self._operations: dict[str, EmailOperation] = {}
        self._events: list[EmailOperationEvent] = []

    def save_operation(self, operation: EmailOperation) -> None:
        operation.updated_at = datetime.now(timezone.utc)
        self._operations[operation.operation_id] = operation

    def get_operation(self, operation_id: str) -> EmailOperation:
        return self._operations[operation_id]

    def list_operations(self) -> list[EmailOperation]:
        return list(self._operations.values())

    def append_event(self, event: EmailOperationEvent) -> None:
        self._events.append(event)

    def list_events(self, operation_id: str | None = None) -> list[EmailOperationEvent]:
        if operation_id is None:
            return list(self._events)
        return [event for event in self._events if event.operation_id == operation_id]

    def list_dead_letters(self) -> list[EmailOperation]:
        return [
            operation
            for operation in self._operations.values()
            if operation.status == EmailOperationStatus.DEAD_LETTER
        ]


class FakeEmailDeliveryGateway:
    """Gateway fake para CI e testes deterministico."""

    def __init__(self, *, fail_times: int = 0, provider: str = "fake") -> None:
        self.fail_times = fail_times
        self.provider = provider
        self.calls = 0

    def send(self, request: EmailDeliveryRequest) -> EmailDeliveryResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            return EmailDeliveryResult(
                success=False,
                provider=self.provider,
                error_message="simulated delivery failure",
                latency_ms=1,
            )
        return EmailDeliveryResult(
            success=True,
            provider=self.provider,
            provider_message_id=f"fake-{request.correlation_id}-{self.calls}",
            latency_ms=1,
        )


class EmailOperationsCenter:
    """Orquestrador de fila, retry, DLQ, replay, timeline e metricas."""

    def __init__(
        self,
        *,
        repository: InMemoryEmailOperationsRepository | None = None,
        gateway: EmailDeliveryGateway,
    ) -> None:
        self.repository = repository or InMemoryEmailOperationsRepository()
        self.gateway = gateway

    def enqueue(self, request: EmailDeliveryRequest) -> EmailOperation:
        request.validate()
        operation = EmailOperation(operation_id=str(uuid4()), request=request)
        self.repository.save_operation(operation)
        self._record_event(
            operation=operation,
            status=EmailOperationStatus.QUEUED,
            severity=EmailOperationSeverity.INFO,
            message="Email delivery request queued.",
        )
        return operation

    def process_next(self) -> EmailOperation | None:
        queued = [
            operation
            for operation in self.repository.list_operations()
            if operation.status in {EmailOperationStatus.QUEUED, EmailOperationStatus.RETRY_SCHEDULED, EmailOperationStatus.REPLAYED}
        ]
        if not queued:
            return None
        operation = sorted(queued, key=lambda item: item.created_at)[0]
        return self._process(operation)

    def replay_dead_letter(self, operation_id: str) -> EmailOperation:
        operation = self.repository.get_operation(operation_id)
        if operation.status != EmailOperationStatus.DEAD_LETTER:
            raise ValueError("only dead-letter operations can be replayed")
        operation.status = EmailOperationStatus.REPLAYED
        operation.last_error = None
        self.repository.save_operation(operation)
        self._record_event(
            operation=operation,
            status=EmailOperationStatus.REPLAYED,
            severity=EmailOperationSeverity.WARNING,
            message="Dead-letter operation replay requested.",
        )
        return operation

    def metrics(self) -> EmailOperationsMetrics:
        operations = self.repository.list_operations()
        return EmailOperationsMetrics(
            queued=sum(1 for item in operations if item.status == EmailOperationStatus.QUEUED),
            processing=sum(1 for item in operations if item.status == EmailOperationStatus.PROCESSING),
            sent=sum(1 for item in operations if item.status == EmailOperationStatus.SENT),
            retry_scheduled=sum(1 for item in operations if item.status == EmailOperationStatus.RETRY_SCHEDULED),
            dead_letter=sum(1 for item in operations if item.status == EmailOperationStatus.DEAD_LETTER),
            failed=sum(1 for item in operations if item.status == EmailOperationStatus.FAILED),
            replayed=sum(1 for item in operations if item.status == EmailOperationStatus.REPLAYED),
        )

    def timeline(self, operation_id: str | None = None) -> list[EmailOperationEvent]:
        return self.repository.list_events(operation_id)

    def dead_letters(self) -> list[EmailOperation]:
        return self.repository.list_dead_letters()

    def _process(self, operation: EmailOperation) -> EmailOperation:
        operation.status = EmailOperationStatus.PROCESSING
        operation.attempts += 1
        self.repository.save_operation(operation)
        self._record_event(
            operation=operation,
            status=EmailOperationStatus.PROCESSING,
            severity=EmailOperationSeverity.INFO,
            message=f"Delivery attempt {operation.attempts} started.",
        )

        result = self.gateway.send(operation.request)
        if result.success:
            operation.status = EmailOperationStatus.SENT
            operation.provider_message_id = result.provider_message_id
            operation.last_error = None
            self.repository.save_operation(operation)
            self._record_event(
                operation=operation,
                status=EmailOperationStatus.SENT,
                severity=EmailOperationSeverity.INFO,
                message="Email delivered successfully.",
                metadata={
                    "provider": result.provider,
                    "provider_message_id": result.provider_message_id or "",
                    "latency_ms": str(result.latency_ms or 0),
                },
            )
            return operation

        operation.last_error = result.error_message or "unknown delivery failure"
        if operation.attempts < operation.request.max_attempts:
            operation.status = EmailOperationStatus.RETRY_SCHEDULED
            severity = EmailOperationSeverity.WARNING
            message = "Delivery failed; retry scheduled."
        else:
            operation.status = EmailOperationStatus.DEAD_LETTER
            severity = EmailOperationSeverity.CRITICAL
            message = "Delivery failed; operation moved to dead-letter queue."

        self.repository.save_operation(operation)
        self._record_event(
            operation=operation,
            status=operation.status,
            severity=severity,
            message=message,
            metadata={"provider": result.provider, "error": operation.last_error},
        )
        return operation

    def _record_event(
        self,
        *,
        operation: EmailOperation,
        status: EmailOperationStatus,
        severity: EmailOperationSeverity,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.repository.append_event(
            EmailOperationEvent(
                event_id=str(uuid4()),
                operation_id=operation.operation_id,
                status=status,
                severity=severity,
                correlation_id=operation.request.correlation_id,
                message=message,
                created_at=datetime.now(timezone.utc),
                metadata=metadata or {},
            )
        )
