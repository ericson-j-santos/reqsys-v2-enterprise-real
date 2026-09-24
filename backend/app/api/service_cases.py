from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext, require_admin_or_service_token
from app.db import Base, get_db
from app.domain.service_management import (
    EvidenceReference,
    Impact,
    IncidentProblemRelation,
    InvalidStateTransition,
    ProblemRootCause,
    ServiceCase,
    ServiceCaseState,
    ServiceCaseType,
    ServiceManagementValidationError,
    Urgency,
    validate_incident_problem_relation,
    validate_problem_root_cause,
)
from app.models.gestao_ti import ServicoTI

logger = logging.getLogger('reqsys.rsm.service_cases')
router = APIRouter(prefix='/v1/service-cases', tags=['ReqSys Service Management'])
require_service_case_auth = require_admin_or_service_token('service_cases:write')


def _safe_log_value(value: object) -> str:
    return str(value).replace('\r', '').replace('\n', '')


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


class IncidentProblemLinkRecord(Base):
    __tablename__ = 'rsm_incident_problem_links'
    __table_args__ = (
        UniqueConstraint(
            'incident_case_id',
            'problem_case_id',
            name='uq_rsm_incident_problem_link',
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    problem_case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProblemRootCauseRecord(Base):
    __tablename__ = 'rsm_problem_root_causes'

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    statement: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IncidentProblemLinkRequest(BaseModel):
    problem_case_id: UUID
    event_id: UUID


class ProblemRootCauseRequest(BaseModel):
    event_id: UUID
    statement: str = Field(min_length=1, max_length=2000)
    evidence_uri: str = Field(min_length=1, max_length=1000)
    evidence_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


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


_PUBLIC_CONFLICT_DETAILS = frozenset(
    {
        'operação CHANGE rejeitada por pré-condição',
        'transição PENDING_APPROVAL -> IN_PROGRESS exige aprovação APPROVED',
    }
)


def _public_conflict_detail(exc: Exception) -> str:
    """Preserva apenas contratos públicos conhecidos; nunca ecoa erro arbitrário."""
    if len(exc.args) == 1 and isinstance(exc.args[0], str):
        candidate = exc.args[0]
        if candidate in _PUBLIC_CONFLICT_DETAILS:
            return candidate
    return 'conflito de estado ou identidade RSM'


TransitionGuard = Callable[[Session, 'ServiceCaseRecord', ServiceCaseState], None]

# Pré-condições adicionais de transição registradas por adaptadores (ex.: portão de
# aprovação do RSM-04). Mantém este módulo sem dependência dos módulos que o estendem.
TRANSITION_GUARDS: list[TransitionGuard] = []


def register_transition_guard(guard: TransitionGuard) -> None:
    """Registra uma pré-condição de transição de forma idempotente."""
    if guard not in TRANSITION_GUARDS:
        TRANSITION_GUARDS.append(guard)


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
        # A UI consome este contrato em vez de duplicar a máquina de estados.
        'allowed_transitions': sorted(item.value for item in _domain(record).allowed_transitions()),
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
            _safe_log_value(existing.case_id),
            _safe_log_value(correlation_id),
            _safe_log_value(payload.source),
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
    db.add(record)
    try:
        db.flush()
        db.add(event)
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
        _safe_log_value(record.case_id),
        _safe_log_value(correlation_id),
        _safe_log_value(record.source),
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

    for guard in TRANSITION_GUARDS:
        guard(db, record, target)

    from_state = record.state
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
            from_state=from_state,
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
        _safe_log_value(case_id),
        _safe_log_value(from_state),
        _safe_log_value(refreshed.state),
        refreshed.version,
        _safe_log_value(correlation_id),
    )
    return refreshed, False


def _serialize_incident_problem_link(record: IncidentProblemLinkRecord) -> dict:
    return {
        'event_id': record.event_id,
        'incident_case_id': record.incident_case_id,
        'problem_case_id': record.problem_case_id,
        'correlation_id': record.correlation_id,
        'created_at': record.created_at.isoformat() if record.created_at else None,
    }


def _serialize_root_cause(record: ProblemRootCauseRecord) -> dict:
    return {
        'event_id': record.event_id,
        'problem_case_id': record.problem_case_id,
        'statement': record.statement,
        'evidence_uri': record.evidence_uri,
        'evidence_sha256': record.evidence_sha256,
        'correlation_id': record.correlation_id,
        'created_at': record.created_at.isoformat() if record.created_at else None,
    }


def _enrich_problem_context(db: Session, record: ServiceCaseRecord, payload: dict) -> None:
    related_cases: list[dict] = []
    if record.case_type == ServiceCaseType.INCIDENT.value:
        links = (
            db.query(IncidentProblemLinkRecord)
            .filter(IncidentProblemLinkRecord.incident_case_id == record.case_id)
            .order_by(IncidentProblemLinkRecord.created_at, IncidentProblemLinkRecord.event_id)
            .all()
        )
        for link in links:
            related = db.get(ServiceCaseRecord, link.problem_case_id)
            if related is not None:
                related_cases.append(
                    {
                        'relation': 'INCIDENT_TO_PROBLEM',
                        'case_id': related.case_id,
                        'case_type': related.case_type,
                        'event_id': link.event_id,
                        'correlation_id': link.correlation_id,
                    }
                )
    elif record.case_type == ServiceCaseType.PROBLEM.value:
        links = (
            db.query(IncidentProblemLinkRecord)
            .filter(IncidentProblemLinkRecord.problem_case_id == record.case_id)
            .order_by(IncidentProblemLinkRecord.created_at, IncidentProblemLinkRecord.event_id)
            .all()
        )
        for link in links:
            related = db.get(ServiceCaseRecord, link.incident_case_id)
            if related is not None:
                related_cases.append(
                    {
                        'relation': 'PROBLEM_FROM_INCIDENT',
                        'case_id': related.case_id,
                        'case_type': related.case_type,
                        'event_id': link.event_id,
                        'correlation_id': link.correlation_id,
                    }
                )
    payload['related_cases'] = related_cases

    if record.case_type == ServiceCaseType.PROBLEM.value:
        causes = (
            db.query(ProblemRootCauseRecord)
            .filter(ProblemRootCauseRecord.problem_case_id == record.case_id)
            .order_by(ProblemRootCauseRecord.created_at, ProblemRootCauseRecord.event_id)
            .all()
        )
        payload['root_causes'] = [_serialize_root_cause(item) for item in causes]
    else:
        payload['root_causes'] = []


def link_incident_to_problem(
    db: Session,
    incident_case_id: str,
    payload: IncidentProblemLinkRequest,
    *,
    correlation_id: str,
) -> tuple[IncidentProblemLinkRecord, bool]:
    event_id = str(payload.event_id)
    problem_case_id = str(payload.problem_case_id)

    replay = db.get(IncidentProblemLinkRecord, event_id)
    if replay is not None:
        if (
            replay.incident_case_id != incident_case_id
            or replay.problem_case_id != problem_case_id
        ):
            raise ServiceCaseConflictError(
                'event_id já utilizado por outra relação INCIDENT -> PROBLEM'
            )
        return replay, True

    existing_event = db.get(ServiceCaseEventRecord, event_id)
    if existing_event is not None:
        raise ServiceCaseConflictError('event_id já utilizado por outro efeito')

    incident = db.get(ServiceCaseRecord, incident_case_id)
    if incident is None:
        raise ServiceCaseNotFoundError('INCIDENT não encontrado')
    problem = db.get(ServiceCaseRecord, problem_case_id)
    if problem is None:
        raise ServiceCaseNotFoundError('PROBLEM não encontrado')

    relation = IncidentProblemRelation(
        incident_case_id=incident_case_id,
        problem_case_id=problem_case_id,
        correlation_id=correlation_id,
    )
    validate_incident_problem_relation(_domain(incident), _domain(problem), relation)

    logical = (
        db.query(IncidentProblemLinkRecord)
        .filter(
            IncidentProblemLinkRecord.incident_case_id == relation.incident_case_id,
            IncidentProblemLinkRecord.problem_case_id == relation.problem_case_id,
        )
        .first()
    )
    if logical is not None:
        return logical, True

    record = IncidentProblemLinkRecord(
        event_id=event_id,
        incident_case_id=relation.incident_case_id,
        problem_case_id=relation.problem_case_id,
        correlation_id=relation.correlation_id,
    )
    db.add(record)
    db.add(
        ServiceCaseEventRecord(
            event_id=event_id,
            case_id=relation.incident_case_id,
            event_type='INCIDENT_LINKED_TO_PROBLEM',
            from_state=None,
            to_state=None,
            correlation_id=relation.correlation_id,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.get(IncidentProblemLinkRecord, event_id)
        if replay is not None:
            if (
                replay.incident_case_id == relation.incident_case_id
                and replay.problem_case_id == relation.problem_case_id
            ):
                return replay, True
            raise ServiceCaseConflictError('event_id já utilizado por outro efeito') from exc
        if db.get(ServiceCaseEventRecord, event_id) is not None:
            raise ServiceCaseConflictError('event_id já utilizado por outro efeito') from exc
        logical = (
            db.query(IncidentProblemLinkRecord)
            .filter(
                IncidentProblemLinkRecord.incident_case_id == relation.incident_case_id,
                IncidentProblemLinkRecord.problem_case_id == relation.problem_case_id,
            )
            .first()
        )
        if logical is not None:
            return logical, True
        raise ServiceCaseConflictError('relação ou event_id já utilizado') from exc
    db.refresh(record)
    return record, False


def record_problem_root_cause(
    db: Session,
    problem_case_id: str,
    payload: ProblemRootCauseRequest,
    *,
    correlation_id: str,
) -> tuple[ProblemRootCauseRecord, bool]:
    event_id = str(payload.event_id)
    replay = db.get(ProblemRootCauseRecord, event_id)
    if replay is not None:
        same_effect = (
            replay.problem_case_id == problem_case_id
            and replay.statement == payload.statement.strip()
            and replay.evidence_uri == payload.evidence_uri.strip()
            and replay.evidence_sha256 == payload.evidence_sha256
        )
        if not same_effect:
            raise ServiceCaseConflictError('event_id já utilizado por outra causa raiz')
        return replay, True

    existing_event = db.get(ServiceCaseEventRecord, event_id)
    if existing_event is not None:
        raise ServiceCaseConflictError('event_id já utilizado por outro efeito')

    problem = db.get(ServiceCaseRecord, problem_case_id)
    if problem is None:
        raise ServiceCaseNotFoundError('PROBLEM não encontrado')

    evidence = EvidenceReference(
        evidence_id=event_id,
        kind='root-cause',
        uri=payload.evidence_uri,
        sha256=payload.evidence_sha256,
    )
    root_cause = ProblemRootCause(
        problem_case_id=problem_case_id,
        statement=payload.statement,
        evidence=evidence,
        correlation_id=correlation_id,
    )
    validate_problem_root_cause(_domain(problem), root_cause)

    record = ProblemRootCauseRecord(
        event_id=event_id,
        problem_case_id=root_cause.problem_case_id,
        statement=root_cause.statement,
        evidence_uri=root_cause.evidence.uri,
        evidence_sha256=root_cause.evidence.sha256,
        correlation_id=root_cause.correlation_id,
    )
    db.add(record)
    db.add(
        ServiceCaseEventRecord(
            event_id=event_id,
            case_id=root_cause.problem_case_id,
            event_type='PROBLEM_ROOT_CAUSE_RECORDED',
            from_state=None,
            to_state=None,
            correlation_id=root_cause.correlation_id,
            evidence_uri=root_cause.evidence.uri,
            evidence_sha256=root_cause.evidence.sha256,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.get(ProblemRootCauseRecord, event_id)
        if replay is not None:
            same_effect = (
                replay.problem_case_id == problem_case_id
                and replay.statement == root_cause.statement
                and replay.evidence_uri == root_cause.evidence.uri
                and replay.evidence_sha256 == root_cause.evidence.sha256
            )
            if same_effect:
                return replay, True
        raise ServiceCaseConflictError('event_id já utilizado') from exc
    db.refresh(record)
    return record, False


def _raise_http(exc: Exception, *, correlation_id: str | None = None) -> None:
    if isinstance(
        exc,
        (ServiceCaseNotFoundError, ServiceCaseConflictError, InvalidStateTransition,
         ServiceManagementValidationError),
    ):
        logger.warning(
            'rsm_request_rejected error_type=%s correlation_id=%s',
            type(exc).__name__,
            _safe_log_value(correlation_id or 'not-provided'),
        )
    if isinstance(exc, ServiceCaseNotFoundError):
        raise HTTPException(status_code=404, detail='recurso RSM não encontrado') from None
    if isinstance(exc, (ServiceCaseConflictError, InvalidStateTransition)):
        raise HTTPException(status_code=409, detail=_public_conflict_detail(exc)) from None
    if isinstance(exc, ServiceManagementValidationError):
        raise HTTPException(status_code=422, detail='requisição RSM inválida') from None
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
        _raise_http(exc, correlation_id=correlation_id)
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
    _enrich_problem_context(db, record, payload)
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
        _raise_http(exc, correlation_id=correlation_id)
    return ok({'case': _serialize(record), 'duplicate': duplicate}, correlation_id)

@router.post('/{case_id}/problem-links')
def create_problem_link(
    case_id: str,
    payload: IncidentProblemLinkRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = link_incident_to_problem(
            db,
            case_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc, correlation_id=correlation_id)
    return ok(
        {'relation': _serialize_incident_problem_link(record), 'duplicate': duplicate},
        correlation_id,
    )


@router.post('/{case_id}/root-causes')
def create_root_cause(
    case_id: str,
    payload: ProblemRootCauseRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = record_problem_root_cause(
            db,
            case_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc, correlation_id=correlation_id)
    return ok(
        {'root_cause': _serialize_root_cause(record), 'duplicate': duplicate},
        correlation_id,
    )

