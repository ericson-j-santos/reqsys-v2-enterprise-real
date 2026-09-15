from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class TodoEventType(str, Enum):
    CREATED = "todo.created"
    UPDATED = "todo.updated"
    STATUS_CHANGED = "todo.status.changed"
    EVIDENCE_UPDATED = "todo.evidence.updated"
    RECONCILE_REQUESTED = "todo.reconcile.requested"


class TodoStatus(str, Enum):
    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM ANDAMENTO"
    BLOQUEADO = "BLOQUEADO"
    CONCLUIDO = "CONCLUÍDO"
    CANCELADO = "CANCELADO"


class TodoPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TodoE2EStatus(str, Enum):
    NA = "N/A"
    PENDENTE = "PENDENTE"
    PARCIAL = "PARCIAL"
    VALIDADO = "VALIDADO"
    BLOQUEADO = "BLOQUEADO"


class TodoPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    type: str = Field(min_length=1, max_length=100)
    external_id: str | None = Field(default=None, max_length=300)
    status: TodoStatus
    priority: TodoPriority | None = None
    blocker: str | None = Field(default=None, max_length=2000)
    next_action: str | None = Field(default=None, max_length=2000)
    completion_criteria: str | None = Field(default=None, max_length=2000)
    evidence: str | None = Field(default=None, max_length=4000)
    evidence_url: str | None = Field(default=None, max_length=2000)
    e2e_status: TodoE2EStatus | None = None
    origin: str | None = Field(default=None, max_length=500)
    origin_url: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validar_estado_operacional(self) -> "TodoPayload":
        if self.status == TodoStatus.BLOQUEADO:
            if not self.blocker or not self.next_action:
                raise ValueError("TODO BLOQUEADO exige blocker e next_action")
        if self.status == TodoStatus.CONCLUIDO:
            if not self.completion_criteria or not self.evidence:
                raise ValueError("TODO CONCLUÍDO exige completion_criteria e evidence")
        return self


class TodoEventV1(BaseModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    event_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    event_type: TodoEventType
    occurred_at: datetime
    correlation_id: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    project: str = Field(min_length=1, max_length=200)
    producer: str | None = Field(default=None, min_length=1, max_length=200)
    todo: TodoPayload

    @field_validator("occurred_at")
    @classmethod
    def validar_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at exige timezone explícito")
        return value.astimezone(timezone.utc)


class TodoEventAcceptedResponse(BaseModel):
    event_id: str
    job_id: str
    status: str = "queued"
    correlation_id: str
    idempotency_key: str
    duplicate_event: bool = False
    status_url: str
    message: str = "Evento persistido e aceito para processamento assíncrono."
