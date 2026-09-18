"""Caminhos críticos — serviço async_workflow_jobs."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.async_workflow_jobs import (
    AsyncWorkflowJobRequest,
    WorkflowJobStatus,
    build_correlation_id,
    enqueue_async_workflow_job,
    process_async_workflow_job,
    store,
    _safe_headers,
)


def _run(coro):
    return asyncio.run(coro)


def setup_function():
    store._jobs.clear()


def teardown_function():
    store._jobs.clear()


def test_build_correlation_id_gera_quando_ausente():
    generated = build_correlation_id(None)
    assert generated.startswith('async-workflow-')


def test_safe_headers_remove_authorization_e_injeta_correlation():
    headers = _safe_headers({'Authorization': 'secret', 'Cookie': 'x'}, 'corr-async')
    assert 'Authorization' not in headers
    assert headers['X-Correlation-Id'] == 'corr-async'
    assert headers['Content-Type'] == 'application/json'


def test_enqueue_e_process_job_com_sucesso():
    request = AsyncWorkflowJobRequest(
        origem='teste',
        destino_url='https://example.com/hook',
        metodo='POST',
        payload={'ok': True},
        max_attempts=1,
    )
    job = _run(enqueue_async_workflow_job(request, 'corr-job-ok'))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {'accepted': True}

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch('app.services.async_workflow_jobs.httpx.AsyncClient', return_value=mock_client):
        _run(process_async_workflow_job(job.job_id))

    persisted = _run(store.get(job.job_id))
    assert persisted is not None
    assert persisted.status == WorkflowJobStatus.COMPLETED
    assert persisted.response_payload == {'accepted': True}


def test_process_job_inexistente_nao_lanca():
    _run(process_async_workflow_job('job-inexistente'))


def test_process_job_dead_letter_apos_tentativas():
    request = AsyncWorkflowJobRequest(
        origem='teste',
        destino_url='https://example.com/hook',
        metodo='POST',
        payload={},
        max_attempts=2,
    )
    job = _run(enqueue_async_workflow_job(request, 'corr-job-fail'))

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=httpx.ConnectError('offline'))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch('app.services.async_workflow_jobs.httpx.AsyncClient', return_value=mock_client):
        with patch('app.services.async_workflow_jobs.asyncio.sleep', new_callable=AsyncMock):
            _run(process_async_workflow_job(job.job_id))

    persisted = _run(store.get(job.job_id))
    assert persisted is not None
    assert persisted.status == WorkflowJobStatus.DEAD_LETTER
    assert persisted.attempts == 2


def test_process_job_resposta_texto_quando_json_invalido():
    request = AsyncWorkflowJobRequest(
        origem='teste',
        destino_url='https://example.com/hook',
        metodo='POST',
        payload={},
        max_attempts=1,
    )
    job = _run(enqueue_async_workflow_job(request, 'corr-job-text'))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = ValueError('not json')
    mock_response.text = 'plain-text-response'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch('app.services.async_workflow_jobs.httpx.AsyncClient', return_value=mock_client):
        _run(process_async_workflow_job(job.job_id))

    persisted = _run(store.get(job.job_id))
    assert persisted is not None
    assert persisted.response_payload == {'text': 'plain-text-response'}
