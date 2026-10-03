from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TodoStatus = Literal['PENDENTE', 'EM ANDAMENTO', 'BLOQUEADO', 'CONCLUÍDO', 'CANCELADO']
TodoPriority = Literal['P0', 'P1', 'P2', 'P3']
TodoE2EStatus = Literal['N/A', 'PENDENTE', 'PARCIAL', 'VALIDADO', 'BLOQUEADO']
TodoType = Literal['Implementação', 'Correção', 'Validação', 'Ação humana', 'Automação', 'Acompanhamento', 'Decisão']
TodoEventType = Literal[
    'todo.created',
    'todo.updated',
    'todo.status.changed',
    'todo.evidence.updated',
    'todo.reconcile.requested',
]


class TodoGlobalTodo(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    type: TodoType
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

    @model_validator(mode='after')
    def validar_estado_operacional(self) -> 'TodoGlobalTodo':
        if self.status == 'BLOQUEADO' and (not self.blocker or not self.next_action):
            raise ValueError('TODO BLOQUEADO exige blocker e next_action')
        if self.status == 'CONCLUÍDO' and (not self.completion_criteria or not self.evidence):
            raise ValueError('TODO CONCLUÍDO exige completion_criteria e evidence')
        return self


class TodoGlobalUpsertRequest(BaseModel):
    schema_version: Literal['1.0']
    event_id: str = Field(min_length=8, max_length=128, pattern=r'^[A-Za-z0-9._:-]+$')
    event_type: TodoEventType
    occurred_at: datetime
    correlation_id: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    project: str = Field(min_length=1, max_length=200)
    producer: str | None = Field(default=None, min_length=1, max_length=200)
    todo: TodoGlobalTodo

    @field_validator('occurred_at')
    @classmethod
    def validar_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('occurred_at exige timezone explícito')
        return value.astimezone(timezone.utc)


class TodoGlobalUpsertResponse(BaseModel):
    todo_id: str = Field(min_length=1, max_length=300)
    idempotency_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    effect: Literal['created', 'updated', 'unchanged']
    canonical_status: TodoStatus
    readback_verified: bool
