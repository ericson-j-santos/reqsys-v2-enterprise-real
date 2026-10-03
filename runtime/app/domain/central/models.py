"""Modelo canônico da Central Global de Solicitações.

Uma Solicitação de Trabalho é a unidade única de controle operacional:

    solicitação -> causa raiz -> executor -> execução -> validação -> evidência

Todo item carrega obrigatoriamente correlation_id, projeto, ambiente e a causa
raiz à qual pertence, de modo que o estado do trabalho deixe de viver em chats,
issues e planilhas concorrentes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Environment(str, Enum):
    DEV = "dev"
    HML = "hml"
    PROD = "prod"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ExecutorKind(str, Enum):
    """Executores conhecidos pelo roteador.

    ``HUMAN_GATE`` não é um executor automático: marca explicitamente que não
    existe executor seguro e que a próxima ação é humana.
    """

    GITHUB = "github"
    CI_REPAIR = "ci_repair"
    COMMAND_GATEWAY = "command_gateway"
    GRAPH = "graph"
    SQL = "sql"
    DRIVE = "drive"
    DOCS = "docs"
    HUMAN_GATE = "human_gate"


class WorkRequestStatus(str, Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    ADMITTED = "ADMITTED"
    EXECUTING = "EXECUTING"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    EVIDENCED = "EVIDENCED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = frozenset({WorkRequestStatus.EVIDENCED, WorkRequestStatus.CANCELLED})

#: Estados que consomem uma vaga de WIP da causa raiz.
ACTIVE_STATUSES = frozenset(
    {
        WorkRequestStatus.ADMITTED,
        WorkRequestStatus.EXECUTING,
        WorkRequestStatus.AWAITING_EVIDENCE,
    }
)


class WorkRequestInput(BaseModel):
    """Entrada aceita pela Central. O executor nunca é escolhido pelo produtor."""

    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=500)
    project: str = Field(min_length=1, max_length=200)
    environment: Environment = Environment.DEV
    priority: Priority = Priority.P2
    root_cause_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=8, max_length=128)
    signals: list[str] = Field(default_factory=list, max_length=50)
    target_system: str | None = Field(default=None, max_length=120)
    repository: str | None = Field(default=None, max_length=300)
    branch: str | None = Field(default=None, max_length=300)
    sha: str | None = Field(default=None, pattern=r"^[a-f0-9]{7,40}$")
    completion_criteria: str | None = Field(default=None, max_length=2000)
    origin_url: str | None = Field(default=None, max_length=2000)

    @field_validator("signals")
    @classmethod
    def validar_sinais(cls, value: list[str]) -> list[str]:
        limpos = [item.strip() for item in value if item and item.strip()]
        if any(len(item) > 500 for item in limpos):
            raise ValueError("cada sinal deve ter no máximo 500 caracteres")
        return limpos


class WorkRequest(BaseModel):
    """Solicitação de Trabalho canônica, já classificada pelo roteador."""

    request_id: str = Field(min_length=1, max_length=200)
    title: str
    project: str
    environment: Environment
    priority: Priority
    root_cause_id: str
    correlation_id: str
    signals: list[str] = Field(default_factory=list)
    target_system: str | None = None
    repository: str | None = None
    branch: str | None = None
    sha: str | None = None
    completion_criteria: str | None = None
    origin_url: str | None = None

    executor: ExecutorKind
    routing_rule: str
    status: WorkRequestStatus = WorkRequestStatus.RECEIVED
    blocker: str | None = Field(default=None, max_length=2000)
    next_action: str | None = Field(default=None, max_length=2000)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validar_estado_operacional(self) -> "WorkRequest":
        if self.status == WorkRequestStatus.BLOCKED and not (self.blocker and self.next_action):
            raise ValueError("solicitação BLOCKED exige blocker e next_action")
        return self


def agora() -> datetime:
    return datetime.now(timezone.utc)
