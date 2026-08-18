from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.correlation import obter_correlation_id
from app.core.envelope import ok
from app.core.security import require_admin
from app.services.operational_deploy import executar_deploy_dev, preparar_deploy_dev

router = APIRouter(prefix='/v1/admin/operational-deploy', tags=['Operational Deploy'])


class DeployDevInput(BaseModel):
    aplicacao: str
    confirmar: bool = False


@router.get('/catalog')
def catalogo(user: dict = Depends(require_admin)):
    return ok(
        {
            'ambiente': 'development',
            'production_touched': False,
            'approval_mode': 'single_confirmation_dev',
            'aplicacoes': [
                {'id': 'backend', 'titulo': 'Backend ReqSys', 'app_name': 'reqsys-api-dev'},
                {'id': 'frontend', 'titulo': 'Frontend ReqSys', 'app_name': 'reqsys-app-dev'},
            ],
            'acoes': ['status', 'deploy'],
        }
    )


@router.post('/validate')
def validar(body: DeployDevInput, user: dict = Depends(require_admin)):
    try:
        operacao = preparar_deploy_dev(body.aplicacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(operacao.__dict__)


@router.post('/execute')
def executar(body: DeployDevInput, request: Request, user: dict = Depends(require_admin)):
    if not body.confirmar:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Confirmação explícita obrigatória para executar deploy em DEV.',
        )
    try:
        resultado = executar_deploy_dev(body.aplicacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Falha ao acionar execução governada: {exc}',
        ) from exc

    resultado['requested_by'] = user.get('sub')
    resultado['request_correlation_id'] = obter_correlation_id()
    resultado['production_touched'] = False
    return ok(resultado)
