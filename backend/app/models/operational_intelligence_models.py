from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class StatusOperacional(str, Enum):
    saudavel = "SAUDAVEL"
    atencao = "ATENCAO"
    degradado = "DEGRADADO"
    bloqueado = "BLOQUEADO"


class SinalRuntime(BaseModel):
    nome: str
    sucesso: bool
    latencia_ms: int = Field(ge=0)
    retries: int = Field(ge=0)
    falhas_consecutivas: int = Field(ge=0)
    criticidade: str = "media"


class DiagnosticoRuntime(BaseModel):
    status: StatusOperacional
    score: int = Field(ge=0, le=100)
    riscos: list[str]
    recomendacoes: list[str]


class EventoOperacional(BaseModel):
    correlation_id: str
    origem: str
    tipo: str
    ambiente: str = "dev"
    status: StatusOperacional
    score: int = Field(ge=0, le=100)
    mensagem: str
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
