from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.application.services.job_service import JobService
from app.domain.models.job_assincrono import AsyncJobAcceptedResponse, AsyncJobCreateRequest, AsyncJobStatusResponse
from app.infrastructure.repositories.job_repository_memoria import JobNaoEncontradoError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_job_service() -> JobService:  # pragma: no cover - sobrescrito em app.main
    raise RuntimeError("Dependência JobService não configurada.")


@router.post("", response_model=AsyncJobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def criar_job_assincrono(
    request: AsyncJobCreateRequest,
    response: Response,
    service: JobService = Depends(get_job_service),
) -> AsyncJobAcceptedResponse:
    accepted = await service.criar_job(request)
    response.headers["Location"] = accepted.status_url
    return accepted


@router.get("/{job_id}", response_model=AsyncJobStatusResponse)
async def consultar_job_assincrono(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> AsyncJobStatusResponse:
    try:
        return await service.consultar_job(job_id)
    except JobNaoEncontradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.") from exc
