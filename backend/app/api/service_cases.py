from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import Base, get_db
from app.domain.service_management import (
    EvidenceReference,
    Impact,
    InvalidStateTransition,
    ServiceCase,
    ServiceCaseState,
    ServiceCaseType,
    ServiceManagementValidationError,
    Urgency,
)
from app.models.gestao_ti import ServicoTI

logger = logging.getLogger('reqsys.rsm.service_cases')
router = APIRouter(prefix='/v1/service-cases', tags=['ReqSys Service Management'])
require_service_case_auth = require_admin_or_service_token('service_cases:write')


class ServiceCaseRecord(Base):
    __tablename__ = 'rsm_service_cases'

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('gestao_ti_servicos.servico_id'),
        nullable=False,
        index=True,
    )
    requester: Mapped[str] = mapped_column(String(200), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default='reqsys')
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default='1.0.0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ServiceCaseEventRecord(Base):
    __tablename__ = 'rsm_service_case_events'

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    evidence_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceCaseCreateRequest(BaseModel):
    case_type: ServiceCaseType
    service_id: str
    requester: str = Field(min_length=1, max_length=200)
    impact: Impact
    urgency: Urgency
    idempotency_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    event_id: UUID
    source: Literal['reqsys', 'teams'] = 'reqsys'


class ServiceCaseTransitionRequest(BaseModel):
    target_state: ServiceCaseState
    expected_version: int = Field(ge=1)
    event_id: UUID
    evidence_uri: str | None = Field(default=None, min_length=1, max_length=1000)
    evidence_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class ServiceCaseNotFoundError(LookupError):
    pass


class ServiceCaseConflictError(RuntimeError):
    pass


def _serialize(record: ServiceCaseRecord) -> dict:
    return {
        'case_id': record.case_id,
        'case_type': record.case_type,
        'service_id': record.service_id,
        'requester': record.requester,
        'impact': record.impact,
        'urgency': record.urgency,
        'priority': record.priority,
        'state': record.state,
        'source': record.source,
        'correlation_id': record.correlation_id,
        'idempotency_key': record.idempotency_key,
        'version': record.version,
        'schema_version': record.schema_version,
        'created_at': record.created_at.isoformat() if record.created_at else None,
        'updated_at': record.updated_at.isoformat() if record.updated_at else None,
    }


def _domain(record: ServiceCaseRecord) -> ServiceCase:
    return ServiceCase(
        case_id=record.case_id,
        case_type=ServiceCaseType(record.case_type),
        service_id=record.service_id,
        requester=record.requester,
        impact=Impact(record.impact),
        urgency=Urgency(record.urgency),
        correlation_id=record.correlation_id,
        idempotency_key=record.idempotency_key,
        state=ServiceCaseState(record.state),
        schema_version=record.schema_version,
        created_at=datetime.now(timezone.utc),
    )


def _active_service(db: Session, service_id: str) -> ServicoTI:
    service = db.get(ServicoTI, service_id)
    if service is None:
        raise ServiceCaseNotFoundError('serviço não encontrado')
    if not service.ativo:
        raise ServiceCaseConflictError('serviço inativo não aceita novos casos')
    return service


def create_service_case(
    db: Session,
    payload: ServiceCaseCreateRequest,
    *,
    correlation_id: str,
) -> tuple[ServiceCaseRecord, bool]:
    _active_service(db, payload.service_id)
    existing = (
        db.query(ServiceCaseRecord)
        .filter(ServiceCaseRecord.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing is not None:
        logger.info(
            'rsm_case_replay case_id=%s correlation_id=%s source=%s',
            existing.case_id,
            correlation_id,
            payload.source,
        )
        return existing, True

    domain = ServiceCase.create(
        case_type=payload.case_type,
        service_id=payload.service_id,
        requester=payload.requester,
        impact=payload.impact,
        urgency=payload.urgency,
        correlation_id=correlation_id,
        idempotency_key=payload.idempotency_key,
    )
    record = ServiceCaseRecord(
        case_id=domain.case_id,
        case_type=domain.case_type.value,
        service_id=domain.service_id,
        requester=domain.requester,
        impact=domain.impact.value,
        urgency=domain.urgency.value,
        priority=domain.priority.value,
        state=domain.state.value,
        source=payload.source,
        correlation_id=domain.correlation_id,
        idempotency_key=domain.idempotency_key,
        version=1,
        schema_version=domain.schema_version,
    )
    event = ServiceCaseEventRecord(
        event_id=str(payload.event_id),
        case_id=domain.case_id,
        event_type='CASE_CREATED',
        from_state=None,
        to_state=domain.state.value,
        correlation_id=correlation_id,
    )
    db.add_all([record, event])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(ServiceCaseRecord)
            .filter(ServiceCaseRecord.idempotency_key == payload.idempotency_key)
            .first()
        )
        if existing is not None:
            return existing, True
        raise ServiceCaseConflictError('event_id ou identidade já utilizada') from exc
    db.refresh(record)
    logger.info(
        'rsm_case_created case_id=%s correlation_id=%s source=%s',
        record.case_id,
        correlation_id,
        record.source,
    )
    return record, False


def transition_service_case(
    db: Session,
    case_id: str,
    payload: ServiceCaseTransitionRequest,
    *,
    correlation_id: str,
) -> tuple[ServiceCaseRecord, bool]:
    replay_event = db.get(ServiceCaseEventRecord, str(payload.event_id))
    if replay_event is not None:
        if replay_event.case_id != case_id or replay_event.to_state != payload.target_state.value:
            raise ServiceCaseConflictError('event_id já utilizado por outro efeito')
        record = db.get(ServiceCaseRecord, case_id)
        if record is None:
            raise ServiceCaseNotFoundError('ServiceCase não encontrado')
        return record, True

    record = db.get(ServiceCaseRecord, case_id)
    if record is None:
        raise ServiceCaseNotFoundError('ServiceCase não encontrado')
    if record.version != payload.expected_version:
        raise ServiceCaseConflictError(
            f'versão divergente: esperado={payload.expected_version} atual={record.version}'
        )

    domain = _domain(record)
    target = payload.target_state
    if target is ServiceCaseState.RESOLVED:
        if not payload.evidence_uri or not payload.evidence_sha256:
            raise ServiceCaseConflictError('resolução exige evidência objetiva')
        EvidenceReference(
            evidence_id=str(payload.event_id),
            kind='resolution',
            uri=payload.evidence_uri,
            sha256=payload.evidence_sha256,
        )

    updated = domain.transition_to(target)
    stmt = (
        update(ServiceCaseRecord)
        .where(
            ServiceCaseRecord.case_id == case_id,
            ServiceCaseRecord.version == payload.expected_version,
        )
        .values(
            state=updated.state.value,
            version=payload.expected_version + 1,
            updated_at=func.now(),
        )
    )
    result = db.execute(stmt)
    if result.rowcount != 1:
        db.rollback()
        raise ServiceCaseConflictError('atualização concorrente detectada')

    db.add(
        ServiceCaseEventRecord(
            event_id=str(payload.event_id),
            case_id=case_id,
            event_type='STATE_TRANSITIONED',
            from_state=record.state,
            to_state=updated.state.value,
            correlation_id=correlation_id,
            evidence_uri=payload.evidence_uri,
            evidence_sha256=payload.evidence_sha256,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceCaseConflictError('event_id já utilizado') from exc
    refreshed = db.get(ServiceCaseRecord, case_id)
    assert refreshed is not None
    logger.info(
        'rsm_case_transitioned case_id=%s from_state=%s to_state=%s version=%s correlation_id=%s',
        case_id,
        record.state,
        refreshed.state,
        refreshed.version,
        correlation_id,
    )
    return refreshed, False


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, ServiceCaseNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if isinstance(exc, (ServiceCaseConflictError, InvalidStateTransition)):
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if isinstance(exc, ServiceManagementValidationError):
        raise HTTPException(status_code=422, detail=str(exc)) from None
    raise exc


@router.post('')
def create_case(
    payload: ServiceCaseCreateRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = create_service_case(db, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'case': _serialize(record), 'duplicate': duplicate}, correlation_id)


@router.get('/{case_id}')
def get_case(
    case_id: str,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    record = db.get(ServiceCaseRecord, case_id)
    if record is None:
        raise HTTPException(status_code=404, detail='ServiceCase não encontrado')
    events = (
        db.query(ServiceCaseEventRecord)
        .filter(ServiceCaseEventRecord.case_id == case_id)
        .order_by(ServiceCaseEventRecord.created_at, ServiceCaseEventRecord.event_id)
        .all()
    )
    payload = _serialize(record)
    payload['events'] = [
        {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'from_state': event.from_state,
            'to_state': event.to_state,
            'correlation_id': event.correlation_id,
            'evidence_uri': event.evidence_uri,
            'evidence_sha256': event.evidence_sha256,
        }
        for event in events
    ]
    return ok(payload)


@router.post('/{case_id}/transitions')
def transition_case(
    case_id: str,
    payload: ServiceCaseTransitionRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = transition_service_case(
            db,
            case_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc)
    return ok({'case': _serialize(record), 'duplicate': duplicate}, correlation_id)
