from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.security import get_current_user, require_admin
from app.services.actions_runtime_monitor import (
    GitHubActionsClient,
    classificar_runs,
    montar_snapshot_operacional,
    normalizar_run,
)
from app.services.operational_deploy import executar_deploy_dev, preparar_deploy_dev

router = APIRouter(prefix='/v1/actions-runtime', tags=['Actions Runtime Center'])


class RunsSnapshotRequest(BaseModel):
    runs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class DeployDevRequest(BaseModel):
    aplicacao: str
    confirmar: bool = False


@router.get('/status')
def status_actions_runtime(user: dict = Depends(get_current_user)):
    return ok(
        {
            'servico': 'actions-runtime-center',
            'autenticado': True,
            'usuario': user.get('sub'),
            'capacidades': [
                'captura_github_actions',
                'classificacao_operacional',
                'score_saude',
                'pareto_falhas',
                'decisao_operacional',
                'deploy_dev_governado',
            ],
        }
    )


@router.post('/snapshot')
def snapshot_manual(body: RunsSnapshotRequest, user: dict = Depends(get_current_user)):
    return ok(montar_snapshot_operacional(body.runs))


@router.get('/github/runs')
def github_runs(
    repo: str = Query(default='ericson-j-santos/reqsys-v2-enterprise-real', max_length=160),
    branch: str = Query(default='main', max_length=80),
    per_page: int = Query(default=20, ge=1, le=50),
    user: dict = Depends(require_admin),
):
    try:
        runs = GitHubActionsClient().listar_runs(repo=repo, branch=branch, per_page=per_page)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Falha ao consultar GitHub Actions: {exc}',
        ) from exc

    return ok(
        {
            'repo': repo,
            'branch': branch,
            'runs': [run.__dict__ | {'health': run.health} for run in runs],
            'resumo': classificar_runs(runs),
        }
    )


@router.get('/operational-deploy/catalog')
def catalogo_deploy_dev(user: dict = Depends(require_admin)):
    return ok(
        {
            'ambiente': 'development',
            'approval_mode': 'single_confirmation_dev',
            'production_touched': False,
            'aplicacoes': [
                {'id': 'backend', 'titulo': 'Backend ReqSys', 'app_name': 'reqsys-api-dev'},
                {'id': 'frontend', 'titulo': 'Frontend ReqSys', 'app_name': 'reqsys-app-dev'},
            ],
        }
    )


@router.post('/operational-deploy/validate')
def validar_deploy_dev(body: DeployDevRequest, user: dict = Depends(require_admin)):
    try:
        operacao = preparar_deploy_dev(body.aplicacao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(operacao.__dict__)


@router.post('/operational-deploy/execute')
def executar_deploy_dev_api(body: DeployDevRequest, user: dict = Depends(require_admin)):
    if not body.confirmar:
        raise HTTPException(status_code=409, detail='Confirmação explícita obrigatória para deploy em DEV.')
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
    resultado['production_touched'] = False
    return ok(resultado)


@router.post('/webhook/github')
def github_webhook_event(payload: dict[str, Any], user: dict = Depends(require_admin)):
    workflow_run = payload.get('workflow_run') if isinstance(payload, dict) else None
    if not isinstance(workflow_run, dict):
        return ok({'recebido': True, 'tipo': 'evento_nao_workflow_run', 'processado': False})

    run = normalizar_run(workflow_run)
    return ok(
        {
            'recebido': True,
            'processado': True,
            'run': run.__dict__ | {'health': run.health},
            'decisao': classificar_runs([run])['decisao'],
        }
    )
