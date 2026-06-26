from io import BytesIO

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.schemas.agents import AgentGenerateRequest, AgentProvisionRequest
from app.services.agent_generator import (
    PACKAGE_NAME,
    catalogo_agentes,
    gerar_pacote_agentes,
    gerar_zip_bytes,
    montar_arquivos_pacote,
)
from app.services.copilot_studio_provisioner import provisionar_copilot_studio
from app.services.reqsys_orchestrator import (
    OrchestratorDemand,
    classificar_demanda,
    classificar_lote,
    listar_coordenadores,
)

router = APIRouter(prefix='/v1/agents', tags=['Agents'])


class DemandaOrquestradorIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=180)
    descricao: str = Field(default='', max_length=4000)
    origem: str = Field(default='chat', max_length=80)
    prioridade_informada: str | None = Field(default=None, max_length=40)
    ambiente: str | None = Field(default=None, max_length=40)


class LoteDemandasOrquestradorIn(BaseModel):
    demandas: list[DemandaOrquestradorIn] = Field(..., min_length=1, max_length=50)


@router.get('/catalog')
def obter_catalogo_agentes():
    """Retorna o catalogo padrao de agentes do ciclo de vida de software."""
    return ok(catalogo_agentes())


@router.post('/generate')
def gerar_agentes(payload: AgentGenerateRequest):
    """Gera um pacote Copilot Studio para orquestrador e agentes especialistas."""
    return ok(gerar_pacote_agentes(payload))


@router.post('/generate.zip')
def baixar_zip_agentes(payload: AgentGenerateRequest):
    """Gera e retorna o ZIP do pacote Copilot Studio."""
    files = montar_arquivos_pacote(payload)
    zip_bytes = gerar_zip_bytes(files)
    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename={PACKAGE_NAME}.zip'},
    )


@router.post('/provision/copilot-studio')
async def provisionar_agentes_copilot_studio(payload: AgentProvisionRequest):
    """Provisiona o pacote de agentes via conector/webhook ou Dataverse ImportSolution."""
    return ok(await provisionar_copilot_studio(payload))


@router.get('/orchestrator/health')
def health_orquestrador():
    """Health check do roteador central de coordenadores IA."""
    return ok({
        'status': 'ok',
        'service': 'reqsys-orchestrator',
        'schema_version': '1.0.0',
        'mode': 'assistido',
    })


@router.get('/orchestrator/coordinators')
def listar_coordenadores_orquestrador():
    """Lista coordenadores IA por frente operacional."""
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
):
    """Classifica uma demanda e sugere o coordenador IA, backlog, labels e automacoes assistidas."""
    demanda = OrchestratorDemand(
        titulo=payload.titulo,
        descricao=payload.descricao,
        origem=payload.origem,
        prioridade_informada=payload.prioridade_informada,
        ambiente=payload.ambiente,
        correlation_id=x_correlation_id,
    )
    return ok(classificar_demanda(demanda), x_correlation_id)


@router.post('/orchestrator/route/batch')
def rotear_lote_orquestrador(
    payload: LoteDemandasOrquestradorIn,
    x_correlation_id: str | None = Header(default=None),
):
    """Classifica um lote de demandas para alimentar filas tematicas e dashboards operacionais."""
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
