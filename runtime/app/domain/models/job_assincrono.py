from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    RETRYING = "retrying"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class TipoOperacao(str, Enum):
    ENVIAR_RESPOSTA = "enviar_resposta"
    SINCRONIZAR_REQUISITO = "sincronizar_requisito"
    NOTIFICAR_STATUS = "notificar_status"


class MetadataEntrada(BaseModel):
    versao_contrato: str = Field(default="0.6.0")
    correlation_id: str | None = Field(default=None, min_length=3, max_length=120)


class AsyncJobCreateRequest(BaseModel):
    origem: str = Field(min_length=2, max_length=80, examples=["power_automate"])
    tipo_operacao: TipoOperacao
    destino: str = Field(min_length=2, max_length=120, examples=["reqsys_runtime"])
    payload: dict[str, Any] = Field(default_factory=dict)
    destino_url: HttpUrl | None = Field(default=None, description="URL externa opcional para POST via httpx.")
    metadata: MetadataEntrada = Field(default_factory=MetadataEntrada)


class AsyncJobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    correlation_id: str
    status_url: str
    message: str = "Processamento recebido e enfileirado."


class AsyncJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    correlation_id: str
    tentativas: int
    max_tentativas: int
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None
    resultado: dict[str, Any] | None = None


class JobAssincrono(BaseModel):
    job_id: str
    origem: str
    tipo_operacao: TipoOperacao
    destino: str
    payload: dict[str, Any]
    correlation_id: str
    max_tentativas: int
    destino_url: str | None = None
    status: JobStatus = JobStatus.QUEUED
    tentativas: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: str | None = None
    resultado: dict[str, Any] | None = None

    def atualizar_status(self, status: JobStatus, *, erro: str | None = None, resultado: dict[str, Any] | None = None) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if erro is not None:
            self.last_error = erro
        if resultado is not None:
            self.resultado = resultado

    def registrar_tentativa(self) -> None:
        self.tentativas += 1
        self.updated_at = datetime.now(timezone.utc)

    def to_status_response(self) -> AsyncJobStatusResponse:
        return AsyncJobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            correlation_id=self.correlation_id,
            tentativas=self.tentativas,
            max_tentativas=self.max_tentativas,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_error=self.last_error,
            resultado=self.resultado,
        )
