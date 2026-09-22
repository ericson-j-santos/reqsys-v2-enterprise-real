from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TipoProcesso(str, Enum):
    DEMANDA = "demanda"
    SERVICO = "servico"
    DOSSIE = "dossie"


class Severidade(str, Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class UsuarioExecucao(BaseModel):
    id: str
    perfil: str
    escopos: list[str] = Field(default_factory=list)


class EvidenciaEntrada(BaseModel):
    tipo: str
    referencia: str


class ContextoAntecipacao(BaseModel):
    tipo_processo: TipoProcesso
    acao: str
    usuario: UsuarioExecucao
    dados: dict[str, Any]
    correlation_id: str


class ItemValidacao(BaseModel):
    codigo: str
    mensagem: str
    campo: str | None = None
    severidade: Severidade


class ResultadoAntecipacao(BaseModel):
    apto_para_iniciar: bool
    status_validacao: Literal["aprovado", "aprovado_com_alerta", "bloqueado"]
    score_prontidao: int
    bloqueios: list[ItemValidacao] = Field(default_factory=list)
    alertas: list[ItemValidacao] = Field(default_factory=list)
    pendencias: list[str] = Field(default_factory=list)
    correlation_id: str
