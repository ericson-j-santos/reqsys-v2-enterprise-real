from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status

from app.services.async_workflow_jobs import (
    AsyncWorkflowJobRequest,
    build_correlation_id,
    enqueue_async_workflow_job,
    process_async_workflow_job,
    store,
)

router = APIRouter(prefix='/api/workflows/async-httpx', tags=['async-workflows'])


@router.post('/jobs', status_code=status.HTTP_202_ACCEPTED)
async def criar_job_assincrono(
    payload: AsyncWorkflowJobRequest,
    background_tasks: BackgroundTasks,
    x_correlation_id: str | None = Header(default=None),
):
    correlation_id = build_correlation_id(x_correlation_id)
    job = await enqueue_async_workflow_job(payload, correlation_id)
    background_tasks.add_task(process_async_workflow_job, job.job_id)
    return {
        'job_id': job.job_id,
        'status': job.status.value,
        'correlation_id': job.correlation_id,
        'status_url': f'/api/workflows/async-httpx/jobs/{job.job_id}',
        'message': 'Processamento recebido e enfileirado.',
    }


@router.get('/jobs/{job_id}')
async def consultar_job_assincrono(job_id: str):
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job assíncrono não encontrado.')
    return job.to_public_dict()


@router.get('/health')
async def async_workflow_health():
    return {
        'service': 'async-httpx-workflows',
        'status': 'ok',
        'queue_backend': 'in_memory',
        'worker_mode': 'fastapi_background_task',
        'enterprise_upgrade_path': ['redis', 'rabbitmq', 'azure_service_bus'],
    }
