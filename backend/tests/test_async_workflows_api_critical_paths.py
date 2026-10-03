"""Testes de caminhos críticos — API async_workflows (jobs em memória)."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.async_workflows import router
from app.services.async_workflow_jobs import (
    AsyncWorkflowJob,
    AsyncWorkflowJobRequest,
    WorkflowJobStatus,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _sample_job(*, job_id: str = 'job-123', status: WorkflowJobStatus = WorkflowJobStatus.QUEUED) -> AsyncWorkflowJob:
    request = AsyncWorkflowJobRequest(
        origem='test',
        destino_url='https://example.com/hook',
        metodo='POST',
        payload={'ok': True},
    )
    return AsyncWorkflowJob(
        job_id=job_id,
        correlation_id='corr-async-001',
        status=status,
        request=request,
        created_at='2026-06-30T00:00:00Z',
        updated_at='2026-06-30T00:00:00Z',
    )


@patch('app.api.async_workflows.enqueue_async_workflow_job', new_callable=AsyncMock)
def test_criar_job_assincrono_retorna_202(mock_enqueue):
    mock_enqueue.return_value = _sample_job()

    client = _client()
    response = client.post(
        '/api/workflows/async-httpx/jobs',
        json={
            'origem': 'test',
            'destino_url': 'https://example.com/hook',
            'metodo': 'POST',
            'payload': {'ok': True},
        },
        headers={'X-Correlation-Id': 'corr-async-001'},
    )

    assert response.status_code == 202
    body = response.json()
    assert body['job_id'] == 'job-123'
    assert body['correlation_id'] == 'corr-async-001'
    assert '/api/workflows/async-httpx/jobs/job-123' in body['status_url']


@patch('app.api.async_workflows.store.get', new_callable=AsyncMock)
def test_consultar_job_assincrono_404_quando_ausente(mock_get):
    mock_get.return_value = None
    client = _client()

    response = client.get('/api/workflows/async-httpx/jobs/inexistente')

    assert response.status_code == 404


@patch('app.api.async_workflows.store.get', new_callable=AsyncMock)
def test_consultar_job_assincrono_retorna_payload_publico(mock_get):
    mock_get.return_value = _sample_job(job_id='job-456', status=WorkflowJobStatus.COMPLETED)
    client = _client()

    response = client.get('/api/workflows/async-httpx/jobs/job-456')

    assert response.status_code == 200
    assert response.json()['status'] == 'completed'


def test_async_workflow_health_contrato():
    client = _client()
    response = client.get('/api/workflows/async-httpx/health')

    assert response.status_code == 200
    body = response.json()
    assert body['service'] == 'async-httpx-workflows'
    assert body['queue_backend'] == 'in_memory'
