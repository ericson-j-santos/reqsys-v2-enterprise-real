from io import BytesIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

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

router = APIRouter(prefix='/v1/agents', tags=['Agents'])


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
