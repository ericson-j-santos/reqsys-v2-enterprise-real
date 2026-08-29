from typing import Any

from pydantic import BaseModel, Field


class PentahoLoteEntrada(BaseModel):
    origem: str = Field(default='PENTAHO', min_length=1, max_length=64)
    processo: str = Field(min_length=1, max_length=120)
    versaoEntrada: int = Field(default=1, ge=1)
    dataReferencia: str | None = Field(default=None, max_length=10)
    lote: str | None = Field(default=None, max_length=128)
    registros: list[dict[str, Any]] = Field(min_length=1)


class PentahoLoteResposta(BaseModel):
    loteId: str
    correlationId: str
    status: str
    duplicado: bool
    consulta: str


class PentahoLoteStatus(BaseModel):
    loteId: str
    lote: str | None
    correlationId: str
    processo: str
    versaoEntrada: int
    dataReferencia: str | None
    status: str
    registrosRecebidos: int
    registrosAceitos: int
    registrosRejeitados: int
    tentativas: int
    erroCodigo: str | None
    erroMensagem: str | None
    criadoEm: str | None
    atualizadoEm: str | None
    processadoEm: str | None
