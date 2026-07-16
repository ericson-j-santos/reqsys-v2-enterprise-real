"""Endpoints de promocao e restauracao governada de revisoes BPMN."""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.services.process_artifact_repository import (
    ProcessArtifactComparisonError,
    ProcessArtifactNotFoundError,
    VersionedProcessArtifactRepository,
)
from app.services.process_version_governance import (
    ProcessPromotionConflictError,
    ProcessPromotionValidationError,
    ProcessVersionGovernanceService,
)

router = APIRouter()
_repository = VersionedProcessArtifactRepository()
_service = ProcessVersionGovernanceService(repository=_repository)


class PromoteVersionRequest(BaseModel):
    target_version: str = Field(min_length=1, max_length=40)
    actor: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=3, max_length=500)
    expected_current_revision: str | None = Field(default=None, max_length=200)


@router.post("/automatico/processos/{process_id}/versoes/{revision}/promover")
def promover_versao(
    process_id: str,
    revision: str,
    payload: PromoteVersionRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
):
    correlation_id = (x_correlation_id or "diagram-promotion-local").strip()[:160]
    try:
        result = _service.promote(
            process_id=process_id,
            source_revision=revision,
            target_version=payload.target_version,
            actor=payload.actor,
            reason=payload.reason,
            correlation_id=correlation_id,
            expected_current_revision=payload.expected_current_revision,
        )
    except ProcessArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProcessArtifactComparisonError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProcessPromotionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProcessPromotionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(result)


@router.get("/automatico/processos/{process_id}/ativo")
def obter_versao_ativa(process_id: str):
    try:
        active = _service.get_active(process_id)
    except ProcessArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(active)


@router.get("/automatico/processos/{process_id}/auditoria-promocoes")
def listar_auditoria_promocoes(process_id: str):
    events = _service.list_events(process_id)
    return ok({"process_id": process_id, "total": len(events), "events": events})
