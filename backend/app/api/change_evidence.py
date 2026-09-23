"""Persistência/API do ciclo fechado de evidência de CHANGE (RSM-07)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.api.service_cases import (
    ServiceCaseConflictError,
    ServiceCaseEventRecord,
    ServiceCaseNotFoundError,
    ServiceCaseRecord,
    _domain,
    _safe_log_value,
    register_transition_guard,
    require_service_case_auth,
)
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext
from app.db import Base, get_db
from app.domain.change_evidence import (
    ChangeExecutionEvidence,
    ChangeValidationStatus,
    assert_change_can_close,
)
from app.domain.service_management import (
    ChangeCiEvidence,
    ChangeTraceability,
    ExternalReference,
    ExternalReferenceType,
    ServiceCaseState,
    ServiceCaseType,
    ServiceManagementValidationError,
    validate_change_ci,
)

logger = logging.getLogger("reqsys.rsm.change_evidence")
router = APIRouter(tags=["ReqSys Service Management"])

EVENT_CHANGE_RUNTIME_EVIDENCE = "CHANGE_RUNTIME_EVIDENCE_RECORDED"
_GIT_SHA_PATTERN = r"^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$"
_SHA256_PATTERN = r"^[a-f0-9]{64}$"


class ChangeEvidenceRecord(Base):
    __tablename__ = "rsm_change_execution_evidence"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rsm_service_cases.case_id"),
        nullable=False,
        index=True,
    )
    requirement_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    sdd_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    pull_request_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ci_run_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ci_conclusion: Mapped[str] = mapped_column(String(40), nullable=False)
    deployment_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    environment: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    runtime_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    post_deploy_evidence_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    post_deploy_evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    rollback_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rollback_runtime_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollback_evidence_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rollback_evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ChangeEvidenceRequest(BaseModel):
    event_id: UUID
    requirement_ref: str = Field(min_length=1, max_length=200)
    sdd_ref: str = Field(min_length=1, max_length=300)
    pull_request_ref: str = Field(min_length=1, max_length=200)
    head_sha: str = Field(pattern=_GIT_SHA_PATTERN)
    ci_run_id: str = Field(min_length=1, max_length=120)
    ci_conclusion: Literal["success"] = "success"
    deployment_ref: str = Field(min_length=1, max_length=300)
    environment: str = Field(min_length=1, max_length=80)
    runtime_sha: str = Field(pattern=_GIT_SHA_PATTERN)
    post_deploy_evidence_uri: str = Field(min_length=1, max_length=1000)
    post_deploy_evidence_sha256: str = Field(pattern=_SHA256_PATTERN)
    status: ChangeValidationStatus
    observed_at: datetime
    rollback_ref: str | None = Field(default=None, min_length=1, max_length=300)
    rollback_runtime_sha: str | None = Field(default=None, pattern=_GIT_SHA_PATTERN)
    rollback_evidence_uri: str | None = Field(default=None, min_length=1, max_length=1000)
    rollback_evidence_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)


def _fingerprint(payload: ChangeEvidenceRequest) -> str:
    values = (
        str(payload.event_id),
        payload.requirement_ref.strip(),
        payload.sdd_ref.strip(),
        payload.pull_request_ref.strip(),
        payload.head_sha.lower(),
        payload.ci_run_id.strip(),
        payload.ci_conclusion,
        payload.deployment_ref.strip(),
        payload.environment.strip(),
        payload.runtime_sha.lower(),
        payload.post_deploy_evidence_uri.strip(),
        payload.post_deploy_evidence_sha256,
        payload.status.value,
        payload.observed_at.isoformat(),
        payload.rollback_ref or "",
        (payload.rollback_runtime_sha or "").lower(),
        payload.rollback_evidence_uri or "",
        payload.rollback_evidence_sha256 or "",
    )
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def _execution_evidence(payload: ChangeEvidenceRequest) -> ChangeExecutionEvidence:
    return ChangeExecutionEvidence(
        head_sha=payload.head_sha,
        deployment_ref=payload.deployment_ref,
        environment=payload.environment,
        runtime_sha=payload.runtime_sha,
        post_deploy_evidence_uri=payload.post_deploy_evidence_uri,
        post_deploy_evidence_sha256=payload.post_deploy_evidence_sha256,
        status=payload.status,
        observed_at=payload.observed_at,
        rollback_ref=payload.rollback_ref,
        rollback_runtime_sha=payload.rollback_runtime_sha,
        rollback_evidence_uri=payload.rollback_evidence_uri,
        rollback_evidence_sha256=payload.rollback_evidence_sha256,
    )


def _record_evidence(record: ChangeEvidenceRecord) -> ChangeExecutionEvidence:
    return ChangeExecutionEvidence(
        head_sha=record.head_sha,
        deployment_ref=record.deployment_ref,
        environment=record.environment,
        runtime_sha=record.runtime_sha,
        post_deploy_evidence_uri=record.post_deploy_evidence_uri,
        post_deploy_evidence_sha256=record.post_deploy_evidence_sha256,
        status=ChangeValidationStatus(record.status),
        observed_at=(
            record.observed_at
            if record.observed_at.tzinfo is not None
            else record.observed_at.replace(tzinfo=timezone.utc)
        ),
        rollback_ref=record.rollback_ref,
        rollback_runtime_sha=record.rollback_runtime_sha,
        rollback_evidence_uri=record.rollback_evidence_uri,
        rollback_evidence_sha256=record.rollback_evidence_sha256,
    )


def _serialize(record: ChangeEvidenceRecord) -> dict:
    return {
        "event_id": record.event_id,
        "case_id": record.case_id,
        "requirement_ref": record.requirement_ref,
        "sdd_ref": record.sdd_ref,
        "pull_request_ref": record.pull_request_ref,
        "head_sha": record.head_sha,
        "ci_run_id": record.ci_run_id,
        "ci_conclusion": record.ci_conclusion,
        "deployment_ref": record.deployment_ref,
        "environment": record.environment,
        "runtime_sha": record.runtime_sha,
        "post_deploy_evidence_uri": record.post_deploy_evidence_uri,
        "post_deploy_evidence_sha256": record.post_deploy_evidence_sha256,
        "status": record.status,
        "rollback_ref": record.rollback_ref,
        "rollback_runtime_sha": record.rollback_runtime_sha,
        "rollback_evidence_uri": record.rollback_evidence_uri,
        "rollback_evidence_sha256": record.rollback_evidence_sha256,
        "observed_at": record.observed_at.isoformat(),
        "correlation_id": record.correlation_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def record_change_evidence(
    db: Session,
    case_id: str,
    payload: ChangeEvidenceRequest,
    *,
    correlation_id: str,
) -> tuple[ChangeEvidenceRecord, bool]:
    case = db.get(ServiceCaseRecord, case_id)
    if case is None:
        raise ServiceCaseNotFoundError("ServiceCase não encontrado")
    if case.case_type != ServiceCaseType.CHANGE.value:
        raise ServiceCaseConflictError("evidência de CHANGE exige case_type CHANGE")

    payload_sha256 = _fingerprint(payload)
    existing = db.get(ChangeEvidenceRecord, str(payload.event_id))
    if existing is not None:
        if existing.case_id != case_id or existing.payload_sha256 != payload_sha256:
            raise ServiceCaseConflictError("event_id já utilizado por outra evidência")
        return existing, True

    event = db.get(ServiceCaseEventRecord, str(payload.event_id))
    if event is not None:
        raise ServiceCaseConflictError("event_id já utilizado por outro efeito")

    if case.state != ServiceCaseState.RESOLVED.value:
        raise ServiceCaseConflictError(
            "evidência pós-deploy só pode ser registrada com CHANGE em RESOLVED"
        )

    traceability = ChangeTraceability(
        requirement=ExternalReference(
            ExternalReferenceType.REQUIREMENT,
            payload.requirement_ref,
        ),
        sdd=ExternalReference(ExternalReferenceType.SDD, payload.sdd_ref),
        pull_request=ExternalReference(
            ExternalReferenceType.PULL_REQUEST,
            payload.pull_request_ref,
        ),
        head_sha=payload.head_sha,
    )
    ci_evidence = ChangeCiEvidence(
        head_sha=payload.head_sha,
        run_id=payload.ci_run_id,
        conclusion=payload.ci_conclusion,
    )
    validate_change_ci(_domain(case), traceability, ci_evidence)
    execution = _execution_evidence(payload)

    record = ChangeEvidenceRecord(
        event_id=str(payload.event_id),
        case_id=case_id,
        requirement_ref=traceability.requirement.external_id,
        sdd_ref=traceability.sdd.external_id,
        pull_request_ref=traceability.pull_request.external_id,
        head_sha=traceability.head_sha,
        ci_run_id=ci_evidence.run_id,
        ci_conclusion=ci_evidence.conclusion,
        deployment_ref=execution.deployment_ref,
        environment=execution.environment,
        runtime_sha=execution.runtime_sha,
        post_deploy_evidence_uri=execution.post_deploy_evidence_uri,
        post_deploy_evidence_sha256=execution.post_deploy_evidence_sha256,
        status=execution.status.value,
        rollback_ref=execution.rollback_ref,
        rollback_runtime_sha=execution.rollback_runtime_sha,
        rollback_evidence_uri=execution.rollback_evidence_uri,
        rollback_evidence_sha256=execution.rollback_evidence_sha256,
        observed_at=execution.observed_at,
        correlation_id=correlation_id,
        payload_sha256=payload_sha256,
    )
    db.add(record)
    db.add(
        ServiceCaseEventRecord(
            event_id=str(payload.event_id),
            case_id=case_id,
            event_type=EVENT_CHANGE_RUNTIME_EVIDENCE,
            from_state=None,
            to_state=None,
            correlation_id=correlation_id,
            evidence_uri=execution.post_deploy_evidence_uri,
            evidence_sha256=execution.post_deploy_evidence_sha256,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        persisted = db.get(ChangeEvidenceRecord, str(payload.event_id))
        if (
            persisted is not None
            and persisted.case_id == case_id
            and persisted.payload_sha256 == payload_sha256
        ):
            return persisted, True
        raise ServiceCaseConflictError("evidência concorrente ou event_id duplicado") from exc

    db.refresh(record)
    logger.info(
        "rsm_change_evidence_recorded case_id=%s head_sha=%s runtime_sha=%s status=%s environment=%s correlation_id=%s",
        _safe_log_value(case_id),
        _safe_log_value(record.head_sha),
        _safe_log_value(record.runtime_sha),
        _safe_log_value(record.status),
        _safe_log_value(record.environment),
        _safe_log_value(correlation_id),
    )
    return record, False


def _change_close_guard(
    db: Session,
    record: ServiceCaseRecord,
    target: ServiceCaseState,
) -> None:
    if record.case_type != ServiceCaseType.CHANGE.value:
        return
    if target is not ServiceCaseState.CLOSED:
        return

    latest = (
        db.query(ChangeEvidenceRecord)
        .filter(ChangeEvidenceRecord.case_id == record.case_id)
        .order_by(
            ChangeEvidenceRecord.observed_at.desc(),
            ChangeEvidenceRecord.created_at.desc(),
            ChangeEvidenceRecord.event_id.desc(),
        )
        .first()
    )
    try:
        assert_change_can_close(_record_evidence(latest) if latest else None)
    except ServiceManagementValidationError as exc:
        raise ServiceCaseConflictError(
            "operação CHANGE rejeitada por pré-condição"
        ) from exc


register_transition_guard(_change_close_guard)


def _raise_http(exc: Exception) -> None:
    """Converte falhas conhecidas sem expor texto interno da exceção."""
    if isinstance(exc, ServiceCaseNotFoundError):
        raise HTTPException(status_code=404, detail="recurso RSM não encontrado") from None
    if isinstance(exc, ServiceCaseConflictError):
        raise HTTPException(
            status_code=409,
            detail="operação CHANGE rejeitada por pré-condição",
        ) from None
    if isinstance(exc, ServiceManagementValidationError):
        raise HTTPException(
            status_code=422,
            detail="evidência CHANGE inválida",
        ) from None
    raise exc


@router.post("/v1/service-cases/{case_id}/change-evidence")
def create_change_evidence(
    case_id: str,
    payload: ChangeEvidenceRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = record_change_evidence(
            db,
            case_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc)
    return ok(
        {"change_evidence": _serialize(record), "duplicate": duplicate},
        correlation_id,
    )


@router.get("/v1/service-cases/{case_id}/change-evidence")
def read_change_evidence(
    case_id: str,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    case = db.get(ServiceCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="ServiceCase não encontrado")
    if case.case_type != ServiceCaseType.CHANGE.value:
        raise HTTPException(status_code=409, detail="case_type não é CHANGE")

    records = (
        db.query(ChangeEvidenceRecord)
        .filter(ChangeEvidenceRecord.case_id == case_id)
        .order_by(
            ChangeEvidenceRecord.observed_at,
            ChangeEvidenceRecord.created_at,
            ChangeEvidenceRecord.event_id,
        )
        .all()
    )
    return ok(
        {
            "case_id": case_id,
            "state": case.state,
            "evidence": [_serialize(record) for record in records],
        }
    )
