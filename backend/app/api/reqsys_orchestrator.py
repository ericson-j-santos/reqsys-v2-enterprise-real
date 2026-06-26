from pydantic import BaseModel, Field
from fastapi import APIRouter, Header

from app.core.envelope import ok
from app.services.reqsys_orchestrator import (
    OrchestratorDemand,
    classificar_demanda,
    classificar_lote,
    listar_coordenadores,
)


router = APIRouter(prefix='/v1/orchestrator', tags=['ReqSys Orchestrator'])


class DemandaOrquestradorIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=180)
    descricao: str = Field(default='', max_length=4000)
    origem: str = Field(default='chat', max_length=80)
    prioridade_informada: str | None = Field(default=None, max_length=40)
    ambiente: str | None = Field(default=None, max_length=40)


class LoteDemandasOrquestradorIn(BaseModel):
    demandas: list[DemandaOrquestradorIn] = Field(..., min_length=1, max_length=50)


@router.get('/health')
def health():
    return ok({
        'status': 'ok',
        'service': 'reqsys-orchestrator',
        'schema_version': '1.0.0',
        'mode': 'assistido',
    })


@router.get('/coordinators')
def coordenadores():
    return ok({
        'schema_version': '1.0.0',
        'total': len(listar_coordenadores()),
        'coordinators': listar_coordenadores(),
    })


@router.post('/route')
def rotear_demanda(payload: DemandaOrquestradorIn, x_correlation_id: str | None = Header(default=None)):
    demanda = OrchestratorDemand(
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=payload.origem,
        prioridade_informada=payload.prioridade_informada,
        ambiente=payload.ambiente,
        correlation_id=x_correlation_id,
    )
    return ok(classificar_demanda(demanda), x_correlation_id)


@router.post('/route/batch')
def rotear_lote(payload: LoteDemandasOrquestradorIn, x_correlation_id: str | None = Header(default=None)):
    demandas = [
        OrchestratorDemand(
            titulo=item.titulo,
            descricao=item.descricao,
            origem=item.origem,
            prioridade_informada=item.prioridade_informada,
            ambiente=item.ambiente,
            correlation_id=x_correlation_id,
        )
        for item in payload.demandas
    ]
    return ok(classificar_lote(demandas), x_correlation_id)
