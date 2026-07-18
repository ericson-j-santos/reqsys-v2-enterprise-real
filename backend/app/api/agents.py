from io import BytesIO

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.envelope import ok
from app.db import get_db
from app.schemas.agents import AgentGenerateRequest, AgentProvisionRequest
from app.services.adr_orchestrator import (
    AdrDemand,
    analytics_adrs,
    coordenar_e_persistir_demanda,
    coordenar_e_persistir_lote,
    listar_coordenadores_adr,
)
from app.services.adr_orchestrator import (
    analytics_coordinators as adr_analytics_coordinators,
)
from app.services.adr_orchestrator import analytics_risk as adr_analytics_risk
from app.services.adr_orchestrator import analytics_summary as adr_analytics_summary
from app.services.agent_generator import (
    PACKAGE_NAME,
    catalogo_agentes,
    gerar_pacote_agentes,
    gerar_zip_bytes,
    montar_arquivos_pacote,
)
from app.services.agile_package_registry import (
    get_package,
    list_packages,
    persist_package,
)
from app.services.agile_project_intelligence import (
    AgileProjectDemand,
    gerar_pacote_agil,
)
from app.services.copilot_studio_provisioner import provisionar_copilot_studio
from app.services.reqsys_orchestrator import (
    OrchestratorDemand,
    analytics_coordinators,
    analytics_risk,
    analytics_summary,
    analytics_themes,
    classificar_e_persistir_demanda,
    classificar_e_persistir_lote,
    listar_coordenadores,
)

router = APIRouter(prefix='/v1/agents', tags=['Agents'])


class DemandaOrquestradorIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=180)
    descricao: str = Field(default='', max_length=4000)
    origem: str = Field(default='chat', max_length=80)
    prioridade_informada: str | None = Field(default=None, max_length=40)
    ambiente: str | None = Field(default=None, max_length=40)
    objetivo: str | None = Field(default=None, max_length=1000)
    publico_alvo: str | None = Field(default=None, max_length=180)
    owner: str | None = Field(default=None, max_length=180)


class LoteDemandasOrquestradorIn(BaseModel):
    demandas: list[DemandaOrquestradorIn] = Field(..., min_length=1, max_length=50)


class DemandaAdrIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=180)
    descricao: str = Field(default='', max_length=4000)
    origem: str = Field(default='chat', max_length=80)
    prioridade_informada: str | None = Field(default=None, max_length=40)
    ambiente: str | None = Field(default=None, max_length=40)


class LoteDemandasAdrIn(BaseModel):
    demandas: list[DemandaAdrIn] = Field(..., min_length=1, max_length=50)


def _anexar_pacote_agil(
    db: Session,
    rota: dict,
    payload: DemandaOrquestradorIn,
    correlation_id: str | None,
) -> dict:
    if rota.get('tema') != 'agile_scrum':
        return rota

    pacote = gerar_pacote_agil(
        AgileProjectDemand(
            titulo=payload.titulo,
            descricao=payload.descricao,
            objetivo=payload.objetivo,
            publico_alvo=payload.publico_alvo,
            owner=payload.owner,
            prioridade=payload.prioridade_informada or rota['prioridade_sugerida'],
            correlation_id=correlation_id,
        )
    )
    rota['agile_project_package'] = pacote
    rota['agile_package_registry'] = persist_package(db, pacote)
    return rota


@router.get('/catalog')
def obter_catalogo_agentes():
    return ok(catalogo_agentes())


@router.post('/generate')
def gerar_agentes(payload: AgentGenerateRequest):
    return ok(gerar_pacote_agentes(payload))


@router.post('/generate.zip')
def baixar_zip_agentes(payload: AgentGenerateRequest):
    files = montar_arquivos_pacote(payload)
    zip_bytes = gerar_zip_bytes(files)
    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename={PACKAGE_NAME}.zip'},
    )


@router.post('/provision/copilot-studio')
async def provisionar_agentes_copilot_studio(payload: AgentProvisionRequest):
    return ok(await provisionar_copilot_studio(payload))


@router.get('/orchestrator/health')
def health_orquestrador():
    return ok({
        'status': 'ok',
        'service': 'reqsys-orchestrator',
        'schema_version': '1.1.0',
        'mode': 'assistido',
        'agile_package_registry': 'enabled',
    })


@router.get('/orchestrator/coordinators')
def listar_coordenadores_orquestrador():
    coordenadores = listar_coordenadores()
    return ok({
        'schema_version': '1.0.0',
        'total': len(coordenadores),
        'coordinators': coordenadores,
    })


@router.post('/orchestrator/route')
def rotear_demanda_orquestrador(
    payload: DemandaOrquestradorIn,
    x_correlation_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    demanda = OrchestratorDemand(
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=payload.origem,
        prioridade_informada=payload.prioridade_informada,
        ambiente=payload.ambiente,
        correlation_id=x_correlation_id,
    )
    rota = classificar_e_persistir_demanda(db, demanda)
    return ok(_anexar_pacote_agil(db, rota, payload, x_correlation_id), x_correlation_id)


@router.post('/orchestrator/route/batch')
def rotear_lote_orquestrador(
    payload: LoteDemandasOrquestradorIn,
    x_correlation_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
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
    resultado = classificar_e_persistir_lote(db, demandas)
    resultado['rotas'] = [
        _anexar_pacote_agil(db, rota, item, x_correlation_id)
        for rota, item in zip(resultado['rotas'], payload.demandas, strict=True)
    ]
    return ok(resultado, x_correlation_id)


@router.get('/orchestrator/agile/packages/{package_id}')
def consultar_pacote_agil(package_id: str, db: Session = Depends(get_db)):
    pacote = get_package(db, package_id)
    if pacote is None:
        raise HTTPException(status_code=404, detail='agile_package_not_found')
    return ok(pacote)


@router.get('/orchestrator/agile/packages')
def listar_pacotes_agile(
    correlation_id: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    pacotes = list_packages(db, correlation_id=correlation_id, status=status, limit=limit)
    return ok({'total': len(pacotes), 'packages': pacotes})


@router.get('/orchestrator/analytics/summary')
def resumo_analytics_orquestrador(db: Session = Depends(get_db)):
    return ok(analytics_summary(db))


@router.get('/orchestrator/analytics/themes')
def analytics_temas_orquestrador(db: Session = Depends(get_db)):
    return ok(analytics_themes(db))


@router.get('/orchestrator/analytics/coordinators')
def analytics_coordenadores_orquestrador(db: Session = Depends(get_db)):
    return ok(analytics_coordinators(db))


@router.get('/orchestrator/analytics/risk')
def analytics_risco_orquestrador(db: Session = Depends(get_db)):
    return ok(analytics_risk(db))


@router.get('/adr-orchestrator/health')
def health_coordenacao_adr():
    return ok({
        'status': 'ok',
        'service': 'reqsys-adr-orchestrator',
        'schema_version': '1.0.0',
        'mode': 'assistido',
        'total_adrs_coordenados': len(listar_coordenadores_adr()),
    })


@router.get('/adr-orchestrator/coordinators')
def listar_coordenadores_adr_endpoint():
    coordenadores = listar_coordenadores_adr()
    return ok({
        'schema_version': '1.0.0',
        'coordenacao_geral': 'adr-geral-coordinator',
        'total': len(coordenadores),
        'coordinators': coordenadores,
    })


@router.post('/adr-orchestrator/route')
def rotear_demanda_adr(
    payload: DemandaAdrIn,
    x_correlation_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    demanda = AdrDemand(
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=payload.origem,
        prioridade_informada=payload.prioridade_informada,
        ambiente=payload.ambiente,
        correlation_id=x_correlation_id,
    )
    return ok(coordenar_e_persistir_demanda(db, demanda), x_correlation_id)


@router.post('/adr-orchestrator/route/batch')
def rotear_lote_adr(
    payload: LoteDemandasAdrIn,
    x_correlation_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    demandas = [
        AdrDemand(
            titulo=item.titulo,
            descricao=item.descricao,
            origem=item.origem,
            prioridade_informada=item.prioridade_informada,
            ambiente=item.ambiente,
            correlation_id=x_correlation_id,
        )
        for item in payload.demandas
    ]
    return ok(coordenar_e_persistir_lote(db, demandas), x_correlation_id)


@router.get('/adr-orchestrator/analytics/summary')
def resumo_analytics_adr(db: Session = Depends(get_db)):
    return ok(adr_analytics_summary(db))


@router.get('/adr-orchestrator/analytics/adrs')
def analytics_por_adr(db: Session = Depends(get_db)):
    return ok(analytics_adrs(db))


@router.get('/adr-orchestrator/analytics/coordinators')
def analytics_coordenadores_adr(db: Session = Depends(get_db)):
    return ok(adr_analytics_coordinators(db))


@router.get('/adr-orchestrator/analytics/risk')
def analytics_risco_adr(db: Session = Depends(get_db)):
    return ok(adr_analytics_risk(db))
