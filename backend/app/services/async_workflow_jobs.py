import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger('reqsys.async_workflow_jobs')

DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 3


class WorkflowJobStatus(str, Enum):
    QUEUED = 'queued'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RETRYING = 'retrying'
    DEAD_LETTER = 'dead_letter'


class AsyncWorkflowJobRequest(BaseModel):
    origem: str = Field(default='api', min_length=2, max_length=80)
    destino_url: HttpUrl
    metodo: str = Field(default='POST', pattern='^(POST|PUT|PATCH)$')
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=1.0, le=60.0)
    max_attempts: int = Field(default=MAX_ATTEMPTS, ge=1, le=5)


@dataclass
class AsyncWorkflowJob:
    job_id: str
    correlation_id: str
    status: WorkflowJobStatus
    request: AsyncWorkflowJobRequest
    created_at: str
    updated_at: str
    attempts: int = 0
    response_status_code: int | None = None
    response_payload: Any | None = None
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'correlation_id': self.correlation_id,
            'status': self.status.value,
            'origem': self.request.origem,
            'destino_url': str(self.request.destino_url),
            'metodo': self.request.metodo,
            'attempts': self.attempts,
            'max_attempts': self.request.max_attempts,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'response_status_code': self.response_status_code,
            'response_payload': self.response_payload,
            'error': self.error,
            'events': self.events[-10:],
        }


class InMemoryAsyncWorkflowJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, AsyncWorkflowJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, request: AsyncWorkflowJobRequest, correlation_id: str) -> AsyncWorkflowJob:
        now = _utcnow()
        job = AsyncWorkflowJob(
            job_id=f'reqsys-job-{uuid4()}',
            correlation_id=correlation_id,
            status=WorkflowJobStatus.QUEUED,
            request=request,
            created_at=now,
            updated_at=now,
            events=[_event('queued', 'Job recebido e enfileirado.')],
        )
        async with self._lock:
            self._jobs[job.job_id] = job
        return job

    async def get(self, job_id: str) -> AsyncWorkflowJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job: AsyncWorkflowJob, status: WorkflowJobStatus, event: str, detail: str | None = None) -> None:
        job.status = status
        job.updated_at = _utcnow()
        job.events.append(_event(event, detail or event))
        async with self._lock:
            self._jobs[job.job_id] = job


store = InMemoryAsyncWorkflowJobStore()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _event(name: str, detail: str) -> dict[str, str]:
    return {'name': name, 'detail': detail, 'timestamp': _utcnow()}


def build_correlation_id(header_value: str | None) -> str:
    return header_value.strip() if header_value and header_value.strip() else f'async-workflow-{uuid4()}'


def _safe_headers(headers: dict[str, str], correlation_id: str) -> dict[str, str]:
    blocked = {'authorization', 'cookie', 'set-cookie'}
    sanitized = {key: value for key, value in headers.items() if key.lower() not in blocked}
    sanitized['X-Correlation-Id'] = correlation_id
    sanitized['Content-Type'] = sanitized.get('Content-Type', 'application/json')
    return sanitized


async def enqueue_async_workflow_job(request: AsyncWorkflowJobRequest, correlation_id: str) -> AsyncWorkflowJob:
    return await store.create(request, correlation_id)


async def process_async_workflow_job(job_id: str) -> None:
    job = await store.get(job_id)
    if job is None:
        logger.warning('async_workflow_job_not_found job_id=%s', job_id)
        return

    await store.update(job, WorkflowJobStatus.PROCESSING, 'processing', 'Worker iniciou processamento assíncrono.')

    url = str(job.request.destino_url)
    headers = _safe_headers(job.request.headers, job.correlation_id)
    timeout = httpx.Timeout(job.request.timeout_seconds, connect=min(5.0, job.request.timeout_seconds))

    for attempt in range(1, job.request.max_attempts + 1):
        job.attempts = attempt
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(job.request.metodo, url, json=job.request.payload, headers=headers)
                job.response_status_code = response.status_code
                response.raise_for_status()
                try:
                    job.response_payload = response.json()
                except ValueError:
                    job.response_payload = {'text': response.text[:2000]}

            await store.update(job, WorkflowJobStatus.COMPLETED, 'completed', 'Chamada HTTP concluída com sucesso.')
            logger.info('async_workflow_job_completed job_id=%s correlation_id=%s', job.job_id, job.correlation_id)
            return
        except Exception as exc:  # noqa: BLE001 - captura operacional governada com DLQ lógica
            job.error = f'{type(exc).__name__}: {exc}'
            logger.warning(
                'async_workflow_job_attempt_failed job_id=%s correlation_id=%s attempt=%s error=%s',
                job.job_id,
                job.correlation_id,
                attempt,
                job.error,
            )
            if attempt < job.request.max_attempts:
                await store.update(job, WorkflowJobStatus.RETRYING, 'retrying', f'Tentativa {attempt} falhou; nova tentativa será executada.')
                await asyncio.sleep(min(2 ** attempt, 10))
            else:
                await store.update(job, WorkflowJobStatus.DEAD_LETTER, 'dead_letter', 'Tentativas esgotadas; job enviado para dead-letter lógico.')
