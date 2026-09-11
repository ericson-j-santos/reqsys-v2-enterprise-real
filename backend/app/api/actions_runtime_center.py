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
from app.services.operational_orchestrator import (
    ManifestError,
    OperationalOrchestrator,
    OperationalOrchestratorError,
)

router = APIRouter(prefix='/v1/actions-runtime', tags=['Actions Runtime Center'])


class RunsSnapshotRequest(BaseModel):
    runs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class DeployDevRequest(BaseModel):
    aplicacao: str
    confirmar: bool = False


class OrchestratorCycleRequest(BaseModel):
    sha: str = Field(min_length=1, max_length=80)
    branch: str = Field(default='main', min_length=1, max_length=160)


class OrchestratorExecuteRequest(BaseModel):
    confirmar: bool = False


class WorkflowRunIngestRequest(BaseModel):
    workflow_run: dict[str, Any]
    project: str = Field(default='reqsys', min_length=1, max_length=80)
    environment: str = Field(default='development', min_length=1, max_length=80)


def _operational_orchestrator() -> OperationalOrchestrator:
    return OperationalOrchestrator()


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
                'action_queue',
                'readiness_as_code',
                'evidence_ledger',
                'operational_orchestrator',
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
        raise HTTPException(status_code=409, detail='Confirmação explícita obrigatória para implantação em DEV.')
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


@router.get('/orchestrator/status')
def orchestrator_status(user: dict = Depends(require_admin)):
    try:
        return ok(_operational_orchestrator().status())
    except (ManifestError, OperationalOrchestratorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/orchestrator/readiness')
def orchestrator_readiness(user: dict = Depends(require_admin)):
    try:
        return ok(_operational_orchestrator().readiness())
    except ManifestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/orchestrator/actions')
def orchestrator_actions(
    action_status: str | None = Query(default=None, alias='status', max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(require_admin),
):
    orchestrator = _operational_orchestrator()
    actions = orchestrator.store.list_actions(status=action_status, limit=limit)
    return ok({'items': [item.to_dict() for item in actions], 'total': len(actions)})


@router.get('/orchestrator/evidence')
def orchestrator_evidence(
    correlation_id: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_admin),
):
    orchestrator = _operational_orchestrator()
    evidence = orchestrator.store.list_evidence(correlation_id=correlation_id, limit=limit)
    return ok({'items': [item.to_dict() for item in evidence], 'total': len(evidence)})


@router.post('/orchestrator/cycle')
def orchestrator_cycle(body: OrchestratorCycleRequest, user: dict = Depends(require_admin)):
    try:
        result = _operational_orchestrator().run_cycle(sha=body.sha, branch=body.branch)
    except (ManifestError, OperationalOrchestratorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result['requested_by'] = user.get('sub')
    return ok(result)


@router.post('/orchestrator/actions/{action_id}/execute')
def orchestrator_execute_action(
    action_id: str,
    body: OrchestratorExecuteRequest,
    user: dict = Depends(require_admin),
):
    try:
        result = _operational_orchestrator().execute(action_id, confirm=body.confirmar)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Ação não encontrada.') from exc
    except (ManifestError, OperationalOrchestratorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result['requested_by'] = user.get('sub')
    return ok(result)


@router.post('/orchestrator/ingest/workflow-run')
def orchestrator_ingest_workflow_run(
    body: WorkflowRunIngestRequest,
    user: dict = Depends(require_admin),
):
    try:
        result = _operational_orchestrator().ingest_workflow_run(
            body.workflow_run,
            project=body.project,
            environment=body.environment,
        )
    except OperationalOrchestratorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result['requested_by'] = user.get('sub')
    return ok(result)


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
