from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.services.copilot_memory_install_safety import validar_destino_assistente
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
    _auth=Depends(require_wsjf_auth),
):
    try:
        await validar_destino_assistente(payload.environment_id, payload.environment_url)
        result = await despachar(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(result, result.get('correlation_id'))
