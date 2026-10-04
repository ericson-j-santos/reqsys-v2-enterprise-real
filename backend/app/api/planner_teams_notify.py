from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.service_tokens import require_admin_or_service_token
from app.services.copilot_memory_install_safety import validar_destino_assistente
from app.services.planner_teams_notify_provisioning import (
    EVENTOS,
    PROFILE,
    despachar,
    montar_bundle,
)

router = APIRouter(prefix='/planner-teams-notify', tags=['Hub Low-Code & IA - Planner->Teams'])
require_planner_teams_auth = require_admin_or_service_token('planner_teams_notify:provisionar')


class PlannerTeamsNotifyProvisionRequest(BaseModel):
    environment_id: str = Field(..., min_length=2, max_length=120)
    environment_url: str = Field(..., min_length=8, max_length=500)
    group_id: str = Field(..., min_length=5, max_length=120)
    plan_id: str = Field(..., min_length=5, max_length=200)
    planner_connection_id: str = Field(..., min_length=2, max_length=500)
    teams_team_id: str = Field(..., min_length=2, max_length=120)
    teams_channel_id: str = Field(..., min_length=2, max_length=200)
    teams_connection_id: str = Field(..., min_length=2, max_length=500)
    target_environment: str = Field(default='dev', min_length=2, max_length=40)
    confirmar: bool = False
    correlation_id: str | None = Field(default=None, max_length=80)


@router.get('/contract')
def planner_teams_notify_contract(_auth=Depends(require_planner_teams_auth)):
    return ok(
        {
            'profile': PROFILE,
            'direction': 'Planner -> Teams',
            'eventos': sorted(EVENTOS),
            'writes_back_to_planner': False,
            'target_environment': 'dev',
            'destino': 'canal do Teams escolhido na instalacao (conector Teams, Post as: Flow bot)',
        }
    )


@router.post('/validate')
async def planner_teams_notify_validate(
    payload: PlannerTeamsNotifyProvisionRequest,
    _auth=Depends(require_planner_teams_auth),
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
async def planner_teams_notify_deploy(
    payload: PlannerTeamsNotifyProvisionRequest,
    x_power_automate_token: str | None = Header(default=None, alias='X-Power-Automate-Token'),
    x_power_platform_token: str | None = Header(default=None, alias='X-Power-Platform-Token'),
    _auth=Depends(require_planner_teams_auth),
):
    """Cria/atualiza os fluxos de notificacao de verdade.

    O token Power Platform delegado confirma novamente o ambiente e preserva a
    trava anti-producao. O token Power Automate delegado gerencia os fluxos.
    """
    try:
        await validar_destino_assistente(
            payload.environment_id,
            payload.environment_url,
            user_token=x_power_platform_token,
        )
        result = await despachar(payload.model_dump(), user_token=x_power_automate_token)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(result, result.get('correlation_id'))
