"""Catálogo mínimo RSM-03: Service -> ServiceOffering -> ServiceCase(type=REQUEST).

Adaptador HTTP/persistência do domínio puro em `app/domain/service_catalog.py`.
Reutiliza a abertura de caso já governada em `app/api/service_cases.py`, de modo
que `correlation_id`, `idempotency_key` e replay continuam com semântica única.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from app.api.service_cases import (
    ServiceCaseConflictError,
    ServiceCaseCreateRequest,
    ServiceCaseNotFoundError,
    ServiceCaseRecord,
    _safe_log_value,
    _serialize,
    create_service_case,
    require_service_case_auth,
)
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext
from app.db import Base, get_db
from app.domain.service_catalog import (
    OfferingFieldSchema,
    OfferingInactiveError,
    OfferingSubmissionError,
    normalize_offering_code,
)
from app.domain.service_management import (
    Impact,
    ServiceCaseType,
    ServiceManagementValidationError,
    Urgency,
)
from app.models.gestao_ti import ServicoTI

logger = logging.getLogger('reqsys.rsm.service_catalog')
router = APIRouter(prefix='/v1/service-offerings', tags=['ReqSys Service Management'])


class ServiceOfferingRecord(Base):
    __tablename__ = 'rsm_service_offerings'

    offering_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('gestao_ti_servicos.servico_id'),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    field_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default='1.0.0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ServiceCaseOfferingRecord(Base):
    """Vínculo append-only entre a oferta do catálogo e o caso aberto."""

    __tablename__ = 'rsm_service_case_offerings'

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        primary_key=True,
    )
    offering_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_offerings.offering_id'),
        nullable=False,
        index=True,
    )
    submitted_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceOfferingCreateRequest(BaseModel):
    service_id: str
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    active: bool = True
    field_schema: dict[str, Any] = Field(default_factory=dict)


class OfferingRequestCreate(BaseModel):
    requester: str = Field(min_length=1, max_length=200)
    impact: Impact
    urgency: Urgency
    idempotency_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    event_id: UUID
    source: Literal['reqsys', 'teams'] = 'reqsys'
    fields: dict[str, Any] = Field(default_factory=dict)


def _serialize_offering(record: ServiceOfferingRecord) -> dict:
    return {
        'offering_id': record.offering_id,
        'service_id': record.service_id,
        'code': record.code,
        'name': record.name,
        'description': record.description,
        'active': bool(record.active),
        'field_schema': record.field_schema or {},
        'schema_version': record.schema_version,
        'created_at': record.created_at.isoformat() if record.created_at else None,
        'updated_at': record.updated_at.isoformat() if record.updated_at else None,
    }


def _active_service(db: Session, service_id: str) -> ServicoTI:
    service = db.get(ServicoTI, service_id)
    if service is None:
        raise ServiceCaseNotFoundError('serviço não encontrado')
    if not service.ativo:
        raise ServiceCaseConflictError('serviço inativo não aceita ofertas')
    return service


def _load_offering(db: Session, offering_id: str) -> ServiceOfferingRecord:
    """Carrega a oferta exigindo existência e estado ativo (fail-closed)."""
    record = db.get(ServiceOfferingRecord, offering_id)
    if record is None:
        raise ServiceCaseNotFoundError('oferta não encontrada')
    return record


def register_offering(
    db: Session,
    payload: ServiceOfferingCreateRequest,
    *,
    correlation_id: str,
) -> tuple[ServiceOfferingRecord, bool]:
    """Registra a oferta de forma idempotente por `code`."""
    code = normalize_offering_code(payload.code)
    schema = OfferingFieldSchema.from_dict(payload.field_schema)
    _active_service(db, payload.service_id)

    existing = (
        db.query(ServiceOfferingRecord).filter(ServiceOfferingRecord.code == code).first()
    )
    if existing is not None:
        if existing.service_id != payload.service_id:
            raise ServiceCaseConflictError('code de oferta já usado por outro serviço')
        logger.info(
            'rsm_offering_replay offering_id=%s code=%s correlation_id=%s',
            _safe_log_value(existing.offering_id),
            _safe_log_value(code),
            _safe_log_value(correlation_id),
        )
        return existing, True

    record = ServiceOfferingRecord(
        offering_id=str(uuid4()),
        service_id=payload.service_id,
        code=code,
        name=payload.name.strip(),
        description=(payload.description or '').strip() or None,
        active=payload.active,
        field_schema=schema.to_dict(),
        schema_version=schema.schema_version,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(ServiceOfferingRecord).filter(ServiceOfferingRecord.code == code).first()
        )
        if existing is not None:
            return existing, True
        raise ServiceCaseConflictError('oferta já registrada') from exc
    db.refresh(record)
    logger.info(
        'rsm_offering_registered offering_id=%s code=%s correlation_id=%s',
        _safe_log_value(record.offering_id),
        _safe_log_value(record.code),
        _safe_log_value(correlation_id),
    )
    return record, False


def open_offering_request(
    db: Session,
    offering_id: str,
    payload: OfferingRequestCreate,
    *,
    correlation_id: str,
) -> tuple[ServiceCaseRecord, ServiceCaseOfferingRecord, bool]:
    """Abre um `ServiceCase(type=REQUEST)` a partir de uma oferta ativa."""
    offering = _load_offering(db, offering_id)
    if not offering.active:
        raise OfferingInactiveError('oferta inativa não aceita novas solicitações')
    _active_service(db, offering.service_id)

    schema = OfferingFieldSchema.from_dict(offering.field_schema)
    normalized_fields = schema.validate_submission(payload.fields)

    case_payload = ServiceCaseCreateRequest(
        case_type=ServiceCaseType.REQUEST,
        service_id=offering.service_id,
        requester=payload.requester,
        impact=payload.impact,
        urgency=payload.urgency,
        idempotency_key=payload.idempotency_key,
        event_id=payload.event_id,
        source=payload.source,
    )
    case, duplicate = create_service_case(db, case_payload, correlation_id=correlation_id)

    link = db.get(ServiceCaseOfferingRecord, case.case_id)
    if link is not None:
        if link.offering_id != offering.offering_id:
            raise ServiceCaseConflictError(
                'idempotency_key já vinculada a outra oferta do catálogo'
            )
        logger.info(
            'rsm_offering_request_replay case_id=%s offering_id=%s correlation_id=%s',
            _safe_log_value(case.case_id),
            _safe_log_value(offering.offering_id),
            _safe_log_value(correlation_id),
        )
        return case, link, True

    if duplicate:
        # Caso preexistente sem vínculo de catálogo: não reescrever origem alheia.
        raise ServiceCaseConflictError(
            'idempotency_key já utilizada por caso fora do catálogo'
        )

    link = ServiceCaseOfferingRecord(
        case_id=case.case_id,
        offering_id=offering.offering_id,
        submitted_fields=normalized_fields,
        correlation_id=correlation_id,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing_link = db.get(ServiceCaseOfferingRecord, case.case_id)
        if existing_link is not None:
            return case, existing_link, True
        raise ServiceCaseConflictError('vínculo catálogo -> caso já registrado') from exc
    db.refresh(link)
    logger.info(
        'rsm_offering_request_created case_id=%s offering_id=%s correlation_id=%s',
        _safe_log_value(case.case_id),
        _safe_log_value(offering.offering_id),
        _safe_log_value(correlation_id),
    )
    return case, link, False


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, ServiceCaseNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if isinstance(exc, (OfferingInactiveError, ServiceCaseConflictError)):
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if isinstance(exc, (OfferingSubmissionError, ServiceManagementValidationError)):
        raise HTTPException(status_code=422, detail=str(exc)) from None
    raise exc


@router.post('')
def create_offering(
    payload: ServiceOfferingCreateRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = register_offering(db, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'offering': _serialize_offering(record), 'duplicate': duplicate}, correlation_id)


@router.get('')
def list_offerings(
    active: bool | None = Query(default=None),
    service_id: str | None = Query(default=None),
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    query = db.query(ServiceOfferingRecord)
    if active is not None:
        query = query.filter(ServiceOfferingRecord.active == active)
    if service_id:
        query = query.filter(ServiceOfferingRecord.service_id == service_id)
    records = query.order_by(ServiceOfferingRecord.code).all()
    return ok({'offerings': [_serialize_offering(record) for record in records]})


@router.get('/{offering_id}')
def get_offering(
    offering_id: str,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    record = db.get(ServiceOfferingRecord, offering_id)
    if record is None:
        raise HTTPException(status_code=404, detail='oferta não encontrada')
    return ok({'offering': _serialize_offering(record)})


@router.post('/{offering_id}/requests')
def open_request(
    offering_id: str,
    payload: OfferingRequestCreate,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        case, link, duplicate = open_offering_request(
            db,
            offering_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc)
    return ok(
        {
            'case': _serialize(case),
            'offering_id': link.offering_id,
            'submitted_fields': link.submitted_fields or {},
            'duplicate': duplicate,
        },
        correlation_id,
    )
