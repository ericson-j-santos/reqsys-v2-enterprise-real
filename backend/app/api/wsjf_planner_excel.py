from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.services.copilot_memory_install_safety import validar_destino_assistente
from app.services.wsjf_excel_workbook import (
    diagnosticar_workbook,
    reparar_workbook_do_tenant,
)
from app.services.wsjf_planner_excel_provisioning import (
    LOCAL_FIELDS,
    PROFILE,
    TABLE,
    despachar,
    montar_bundle,
)

router = APIRouter(prefix='/wsjf/planner-excel', tags=['Hub Low-Code & IA - WSJF'])
require_wsjf_auth = require_admin_or_service_token('wsjf_powerautomate:provisionar')


class WsjfPlannerExcelProvisionRequest(BaseModel):
    environment_id: str = Field(..., min_length=2, max_length=120)
    environment_url: str = Field(..., min_length=8, max_length=500)
    group_id: str = Field(..., min_length=5, max_length=120)
    plan_id: str = Field(..., min_length=5, max_length=200)
    excel_source: str = Field(..., min_length=2, max_length=500)
    excel_drive: str = Field(..., min_length=2, max_length=300)
    excel_file: str = Field(..., min_length=2, max_length=500)
    planner_connection_id: str = Field(..., min_length=2, max_length=500)
    excel_connection_id: str = Field(..., min_length=2, max_length=500)
    target_environment: str = Field(default='dev', min_length=2, max_length=40)
    confirmar: bool = False
    correlation_id: str | None = Field(default=None, max_length=80)


class WsjfWorkbookRequest(BaseModel):
    excel_drive: str = Field(..., min_length=2, max_length=300)
    excel_file: str = Field(..., min_length=2, max_length=500)


class WsjfWorkbookRepairRequest(WsjfWorkbookRequest):
    confirmar: bool = False


@router.get('/contract')
def wsjf_planner_excel_contract(_auth=Depends(require_wsjf_auth)):
    return ok(
        {
            'profile': PROFILE,
            'direction': 'Planner -> Excel',
            'planner_is_source_of_truth': True,
            'excel_table': TABLE,
            'local_fields_preserved': sorted(LOCAL_FIELDS),
            'recurrence': '1 hora',
            'writes_back_to_planner': False,
            'target_environment': 'dev',
        }
    )


@router.post('/validate')
async def wsjf_planner_excel_validate(
    payload: WsjfPlannerExcelProvisionRequest,
    _auth=Depends(require_wsjf_auth),
):
    try:
        await validar_destino_assistente(payload.environment_id, payload.environment_url)
        data = payload.model_dump()
        data['confirmar'] = False
        bundle = montar_bundle(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(bundle, bundle['correlation_id'])


@router.post('/deploy')
async def wsjf_planner_excel_deploy(
    payload: WsjfPlannerExcelProvisionRequest,
    x_power_automate_token: str | None = Header(default=None, alias='X-Power-Automate-Token'),
    _auth=Depends(require_wsjf_auth),
):
    """Cria/atualiza o fluxo de verdade. Exige token delegado (via MSAL no
    frontend): a API de gerenciamento de fluxos nao aceita credencial
    app-only."""
    try:
        await validar_destino_assistente(payload.environment_id, payload.environment_url)
        await _garantir_workbook_utilizavel(payload.excel_drive, payload.excel_file)
        result = await despachar(payload.model_dump(), user_token=x_power_automate_token)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(result, result.get('correlation_id'))


async def _garantir_workbook_utilizavel(excel_drive: str, excel_file: str) -> None:
    """Falha antes de instalar quando o WSJF.xlsx do tenant e recusado.

    Sem isso o fluxo e criado com sucesso e so falha depois, em execucao, com
    unsupportedWorkbook — erro que aparece longe do instalador e nao diz o que
    fazer. Bloqueia apenas quando o proprio arquivo e o problema: falha de rede,
    permissao ou 5xx do Graph nao impedem a instalacao.
    """
    try:
        diagnostico = await diagnosticar_workbook(excel_drive, excel_file)
    except ValueError:
        raise
    except Exception:
        return
    if diagnostico.get('precisa_reparo'):
        raise HTTPException(
            status_code=409,
            detail=(
                'O WSJF.xlsx escolhido e recusado pelo motor Excel do Microsoft Graph '
                f"({diagnostico.get('erros_pacote') or diagnostico.get('graph_erro')}). "
                'Use "Regenerar WSJF.xlsx" antes de instalar o fluxo.'
            ),
        )


@router.post('/excel/diagnostico')
async def wsjf_planner_excel_diagnostico(
    payload: WsjfWorkbookRequest,
    _auth=Depends(require_wsjf_auth),
):
    """Diz se o WSJF.xlsx escolhido seria aceito pelo conector Excel do fluxo."""
    try:
        return ok(await diagnosticar_workbook(payload.excel_drive, payload.excel_file))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post('/excel/reparar')
async def wsjf_planner_excel_reparar(
    payload: WsjfWorkbookRepairRequest,
    _auth=Depends(require_wsjf_auth),
):
    """Substitui no tenant um WSJF.xlsx recusado pelo motor Excel do Graph."""
    if not payload.confirmar:
        raise HTTPException(status_code=409, detail='Confirmacao obrigatoria para substituir o WSJF.xlsx do tenant')
    try:
        return ok(await reparar_workbook_do_tenant(payload.excel_drive, payload.excel_file))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
