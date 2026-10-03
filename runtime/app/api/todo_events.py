from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.services.job_service import JobService, TodoEventIdentityConflictError
from app.domain.models.job_assincrono import AsyncJobStatusResponse
from app.domain.models.todo_event import TodoEventAcceptedResponse, TodoEventV1
from app.infrastructure.queue.errors import QueueCapacityError
from app.infrastructure.repositories.job_repository_memoria import JobNaoEncontradoError

router = APIRouter(prefix="/api/todo-events", tags=["todo-events"])
_bearer_optional = HTTPBearer(auto_error=False)


def require_todo_producer_token(
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> bool:
    expected = os.getenv("TODO_GLOBAL_RUNTIME_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TODO Global runtime producer token não configurado.",
        )
    candidate = (x_service_token or (credentials.credentials if credentials else "")).strip()
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de produtor inválido.",
        )
    return True



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
    _authorized: bool = Depends(require_todo_producer_token),
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
    _authorized: bool = Depends(require_todo_producer_token),
    service: JobService = Depends(get_job_service),
) -> AsyncJobStatusResponse:
    try:
        return await service.consultar_todo_evento(event_id)
    except JobNaoEncontradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.") from exc
