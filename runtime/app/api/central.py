"""API da Central Global de Solicitações (plano de controle operacional)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.application.services.central_service import (
    CentralService,
    InvalidTransitionError,
    WorkRequestNotFoundError,
)
from app.domain.central.evidence_ledger import EvidenceRecord, EvidenceRecordInput
from app.domain.central.models import ExecutorKind, WorkRequest, WorkRequestInput, WorkRequestStatus

router = APIRouter(prefix="/api/central", tags=["central"])


def get_central_service() -> CentralService:  # pragma: no cover - sobrescrito em app.main
    raise RuntimeError("Dependência CentralService não configurada.")


class RootCauseSlotView(BaseModel):
    root_cause_id: str
    priority: str
    request_ids: list[str]


class AdmissionPlanView(BaseModel):
    max_active_root_causes: int
    wip_breach: bool
    admitted: list[RootCauseSlotView]
    queued: list[RootCauseSlotView]


class TransitionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    status: WorkRequestStatus
    blocker: str | None = Field(default=None, max_length=2000)
    next_action: str | None = Field(default=None, max_length=2000)


@router.post("/work-requests", response_model=WorkRequest, status_code=status.HTTP_201_CREATED)
async def registrar_solicitacao(
    entrada: WorkRequestInput,
    response: Response,
    service: CentralService = Depends(get_central_service),
) -> WorkRequest:
    solicitacao = await service.registrar(entrada)
    response.headers["X-Correlation-Id"] = solicitacao.correlation_id
    response.headers["Location"] = f"/api/central/work-requests/{solicitacao.request_id}"
    return solicitacao


@router.get("/work-requests", response_model=list[WorkRequest])
async def listar_solicitacoes(service: CentralService = Depends(get_central_service)) -> list[WorkRequest]:
    return list(await service.listar())


@router.get("/work-requests/{request_id}", response_model=WorkRequest)
async def obter_solicitacao(
    request_id: str, service: CentralService = Depends(get_central_service)
) -> WorkRequest:
    try:
        return await service.obter(request_id)
    except WorkRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada.") from exc


@router.post("/work-requests/{request_id}/transition", response_model=WorkRequest)
async def transicionar_solicitacao(
    request_id: str,
    payload: TransitionRequest,
    service: CentralService = Depends(get_central_service),
) -> WorkRequest:
    try:
        return await service.transicionar(
            request_id, payload.status, blocker=payload.blocker, next_action=payload.next_action
        )
    except WorkRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada.") from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/admission-plan", response_model=AdmissionPlanView)
async def obter_plano_admissao(service: CentralService = Depends(get_central_service)) -> AdmissionPlanView:
    snapshot = await service.aplicar_admissao()
    plano = snapshot.plan
    return AdmissionPlanView(
        max_active_root_causes=plano.max_active_root_causes,
        wip_breach=plano.wip_breach,
        admitted=[_slot_view(slot) for slot in plano.admitted],
        queued=[_slot_view(slot) for slot in plano.queued],
    )


@router.get(
    "/next",
    response_model=WorkRequest,
    responses={204: {"description": "Nenhum item executável disponível."}},
)
async def proximo_item(
    executor: ExecutorKind | None = None,
    service: CentralService = Depends(get_central_service),
):
    proximo = await service.proximo_item(executor)
    if proximo is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return proximo


@router.post("/evidence", response_model=EvidenceRecord, status_code=status.HTTP_201_CREATED)
async def registrar_evidencia(
    entrada: EvidenceRecordInput,
    service: CentralService = Depends(get_central_service),
) -> EvidenceRecord:
    try:
        return await service.registrar_evidencia(entrada)
    except WorkRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada.") from exc


@router.get(
    "/evidence/{request_id}",
    response_model=EvidenceRecord,
    responses={404: {"description": "Sem evidência registrada."}},
)
async def obter_evidencia(
    request_id: str, service: CentralService = Depends(get_central_service)
) -> EvidenceRecord:
    registro = await service.obter_evidencia(request_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem evidência registrada.")
    return registro


def _slot_view(slot) -> RootCauseSlotView:
    return RootCauseSlotView(
        root_cause_id=slot.root_cause_id,
        priority=slot.priority.value,
        request_ids=list(slot.request_ids),
    )
