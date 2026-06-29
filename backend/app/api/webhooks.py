import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.envelope import ok
from app.db import get_db
from app.services import figma_client, figma_github_sync, git_parser, webhook_processor
from app.services.agile_git_sync import sincronizar_work_items_git
from app.services.async_workflow_jobs import (
    AsyncWorkflowJobRequest,
    build_correlation_id,
    enqueue_async_workflow_job,
    process_async_workflow_job,
    store as async_workflow_store,
)

router = APIRouter(prefix='/v1/webhooks', tags=['Webhooks Git'])


def _verificar_assinatura_github(body: bytes, signature: str | None) -> None:
    """Valida X-Hub-Signature-256 usando HMAC-SHA256. Se GITHUB_WEBHOOK_SECRET não estiver
    configurado aceita qualquer request — configure o secret em produção."""
    secret = settings.github_webhook_secret
    if not secret:
        return
    if not signature or not signature.startswith('sha256='):
        raise HTTPException(status_code=401, detail='Assinatura GitHub ausente ou malformada.')
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    esperado = 'sha256=' + mac.hexdigest()
    if not hmac.compare_digest(signature, esperado):
        raise HTTPException(status_code=401, detail='Assinatura GitHub inválida.')


def _verificar_token_gitlab(token: str | None) -> None:
    """Valida X-Gitlab-Token. Se GITLAB_WEBHOOK_TOKEN não estiver configurado, aceita."""
    secret = settings.gitlab_webhook_token
    if not secret:
        return
    if not token or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail='Token GitLab inválido.')


@router.post('/github')
async def webhook_github(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Recebe eventos push e pull_request do GitHub.
    Extrai códigos REQ-XXXXXX e cria vínculos de rastreabilidade.
    Configure o secret em: Settings → Webhooks → Secret (GITHUB_WEBHOOK_SECRET no .env).
    """
    body = await request.body()
    _verificar_assinatura_github(body, x_hub_signature_256)

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail='Payload JSON inválido.')

    event = (x_github_event or '').lower()
    vinculos: list[dict] = []
    eventos_agile: list[dict] = []

    if event == 'push':
        vinculos = git_parser.processar_push_github(payload)
        eventos_agile = git_parser.processar_push_github_agile(payload)
    elif event == 'pull_request':
        action = payload.get('action', '')
        if action in ('opened', 'reopened', 'closed', 'edited', 'synchronize'):
            vinculos = git_parser.processar_pr_github(payload)
            eventos_agile = git_parser.processar_pr_github_agile(payload)
    elif event in ('issues', 'issue_comment'):
        sync_result = figma_github_sync.handle_github_issue_event(db, payload)
        return ok({'evento': event, 'processado': True, 'figma_github': sync_result.as_dict()})
    elif event == 'ping':
        return ok({'evento': 'ping', 'processado': True, 'motivo': 'Webhook configurado com sucesso.'})
    else:
        return ok({'evento': event, 'processado': False, 'motivo': 'Evento não suportado.'})

    if not vinculos and not eventos_agile:
        return ok({'evento': event, 'processado': True, 'vinculos_criados': 0,
                   'work_items_atualizados': 0,
                   'motivo': 'Nenhum codigo REQ-* ou AGI-* encontrado nos commits/PR.'})

    ids = webhook_processor.salvar_vinculos(db, vinculos) if vinculos else []
    agile_ids = sincronizar_work_items_git(db, eventos_agile) if eventos_agile else []
    return ok({
        'evento': event,
        'processado': True,
        'vinculos_criados': len(ids),
        'work_items_atualizados': len(agile_ids),
    })


@router.post('/figma')
async def webhook_figma(
    request: Request,
    x_figma_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    body = await request.body()
    try:
        figma_client.validate_webhook_signature(body, x_figma_signature)
    except figma_client.FigmaError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail='Payload JSON invalido.')

    event = (payload.get('event_type') or payload.get('event') or payload.get('type') or '').upper()
    if event == 'PING':
        return ok({'evento': 'PING', 'processado': True, 'motivo': 'Webhook Figma configurado com sucesso.'})

    file_key = payload.get('file_key') or payload.get('fileKey') or payload.get('file', {}).get('key')
    repo = settings.figma_github_default_repo
    if not file_key or not repo:
        return ok({'evento': event or 'unknown', 'processado': False, 'motivo': 'file_key ou repo padrao nao configurado.'})

    result = figma_github_sync.sync_bidirectional(db, file_key=file_key, repo=repo, include_frames=False)
    return ok({'evento': event or 'unknown', 'processado': True, 'figma_github': result.as_dict()})


@router.post('/gitlab')
async def webhook_gitlab(
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    x_gitlab_event: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Recebe eventos Push Hook e Merge Request Hook do GitLab.
    Extrai códigos REQ-XXXXXX e cria vínculos de rastreabilidade.
    Configure em: Settings → Webhooks → Secret token (GITLAB_WEBHOOK_TOKEN no .env).
    """
    body = await request.body()
    _verificar_token_gitlab(x_gitlab_token)

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail='Payload JSON inválido.')

    event = (x_gitlab_event or '').lower()
    vinculos: list[dict] = []
    eventos_agile: list[dict] = []

    if 'push' in event:
        vinculos = git_parser.processar_push_gitlab(payload)
        eventos_agile = git_parser.processar_push_gitlab_agile(payload)
    elif 'merge request' in event:
        vinculos = git_parser.processar_mr_gitlab(payload)
        eventos_agile = git_parser.processar_mr_gitlab_agile(payload)
    else:
        return ok({'evento': event, 'processado': False, 'motivo': 'Evento não suportado.'})

    if not vinculos and not eventos_agile:
        return ok({'evento': event, 'processado': True, 'vinculos_criados': 0,
                   'work_items_atualizados': 0,
                   'motivo': 'Nenhum codigo REQ-* ou AGI-* encontrado nos commits/MR.'})

    ids = webhook_processor.salvar_vinculos(db, vinculos) if vinculos else []
    agile_ids = sincronizar_work_items_git(db, eventos_agile) if eventos_agile else []
    return ok({
        'evento': event,
        'processado': True,
        'vinculos_criados': len(ids),
        'work_items_atualizados': len(agile_ids),
    })


@router.post('/async-httpx/jobs', status_code=status.HTTP_202_ACCEPTED)
async def criar_job_httpx_assincrono(
    payload: AsyncWorkflowJobRequest,
    background_tasks: BackgroundTasks,
    x_correlation_id: str | None = Header(default=None),
):
    correlation_id = build_correlation_id(x_correlation_id)
    job = await enqueue_async_workflow_job(payload, correlation_id)
    background_tasks.add_task(process_async_workflow_job, job.job_id)
    return ok({
        'job_id': job.job_id,
        'status': job.status.value,
        'correlation_id': job.correlation_id,
        'status_url': f'/v1/webhooks/async-httpx/jobs/{job.job_id}',
        'message': 'Processamento recebido e enfileirado.',
    })


@router.get('/async-httpx/jobs/{job_id}')
async def consultar_job_httpx_assincrono(job_id: str):
    job = await async_workflow_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job assíncrono não encontrado.')
    return ok(job.to_public_dict())


@router.get('/async-httpx/health')
async def async_httpx_health():
    return ok({
        'service': 'async-httpx-workflows',
        'status': 'ok',
        'queue_backend': 'in_memory',
        'worker_mode': 'fastapi_background_task',
        'enterprise_upgrade_path': ['redis', 'rabbitmq', 'azure_service_bus'],
    })
