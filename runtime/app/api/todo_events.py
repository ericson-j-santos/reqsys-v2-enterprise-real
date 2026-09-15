from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.application.services.job_service import JobService, TodoEventIdentityConflictError
from app.domain.models.job_assincrono import AsyncJobStatusResponse
from app.domain.models.todo_event import TodoEventAcceptedResponse, TodoEventV1
from app.infrastructure.queue.errors import QueueCapacityError
from app.infrastructure.repositories.job_repository_memoria import JobNaoEncontradoError

router = APIRouter(prefix="/api/todo-events", tags=["todo-events"])


def get_job_service() -> JobService:  # pragma: no cover - sobrescrito em app.main
    raise RuntimeError("Dependência JobService não configurada.")


@router.post(
    "",
    response_model=TodoEventAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        409: {"description": "event_id já existe com conteúdo diferente."},
        503: {"description": "Fila sem capacidade; produtor deve tentar novamente."},
    },
)
async def publicar_todo_evento(
    event: TodoEventV1,
    response: Response,
    service: JobService = Depends(get_job_service),
) -> TodoEventAcceptedResponse:
    try:
        accepted = await service.criar_todo_evento(event)
    except TodoEventIdentityConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="event_id já persistido com conteúdo diferente.",
        ) from exc
    except QueueCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fila temporariamente sem capacidade; evento não foi aceito.",
            headers={"Retry-After": "5"},
        ) from exc
    response.headers["Location"] = accepted.status_url
    response.headers["X-Correlation-Id"] = accepted.correlation_id
    return accepted


@router.get(
    "/{event_id}",
    response_model=AsyncJobStatusResponse,
    responses={404: {"description": "Evento não encontrado."}},
)
async def consultar_todo_evento(
    event_id: str,
    service: JobService = Depends(get_job_service),
) -> AsyncJobStatusResponse:
    try:
        return await service.consultar_todo_evento(event_id)
    except JobNaoEncontradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.") from exc
