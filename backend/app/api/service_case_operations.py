"""Controles operacionais RSM-04: SLA, atribuição, aprovação e histórico auditável.

Adaptador HTTP/persistência do domínio puro em `app/domain/service_operations.py`.

Decisões de projeto:
- nenhuma tabela existente sofre `ALTER`: tudo entra em tabelas novas;
- o histórico reaproveita `rsm_service_case_events` do RSM-02, cuja PK `event_id`
  já garante replay sem segundo efeito para qualquer operação;
- os marcos de SLA (primeira resposta e resolução) são derivados do histórico
  append-only, não gravados em paralelo, evitando duas versões da mesma verdade;
- o portão de aprovação entra por `register_transition_guard`, sem que o módulo
  de casos precise conhecer este módulo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.api.service_cases import (
    ServiceCaseConflictError,
    ServiceCaseEventRecord,
    ServiceCaseNotFoundError,
    ServiceCaseRecord,
    _safe_log_value,
    register_transition_guard,
    require_service_case_auth,
)
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.service_tokens import ServiceAuthContext
from app.db import Base, get_db
from app.domain.service_management import (
    ApprovalStatus,
    ServiceCasePriority,
    ServiceCaseState,
    ServiceManagementValidationError,
    SlaPolicy,
)
from app.domain.service_operations import (
    OPERATIONS_SCHEMA_VERSION,
    ApprovalRequiredError,
    AssignmentValidationError,
    SlaTargets,
    SlaViolationError,
    assert_approval_allows_transition,
    calculate_sla_targets,
    evaluate_sla,
    plan_assignment,
    requires_approval,
    validate_approval_decision,
)

logger = logging.getLogger('reqsys.rsm.operations')
router = APIRouter(tags=['ReqSys Service Management'])

EVENT_SLA_APPLIED = 'SLA_APPLIED'
EVENT_ASSIGNMENT_CHANGED = 'ASSIGNMENT_CHANGED'
EVENT_APPROVAL_REQUESTED = 'APPROVAL_REQUESTED'
EVENT_APPROVAL_DECIDED = 'APPROVAL_DECIDED'


class SlaPolicyRecord(Base):
    __tablename__ = 'rsm_sla_policies'

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseSlaRecord(Base):
    """Prazos absolutos de um caso. Imutável após a aplicação da política."""

    __tablename__ = 'rsm_case_sla'

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        primary_key=True,
    )
    policy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_sla_policies.policy_id'),
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolution_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default=OPERATIONS_SCHEMA_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseAssignmentRecord(Base):
    """Histórico append-only de atribuições. Nenhuma linha é atualizada."""

    __tablename__ = 'rsm_case_assignments'

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_group: Mapped[str] = mapped_column(String(200), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(200), nullable=True)
    previous_group: Mapped[str | None] = mapped_column(String(200), nullable=True)
    previous_assignee: Mapped[str | None] = mapped_column(String(200), nullable=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseApprovalRecord(Base):
    __tablename__ = 'rsm_case_approvals'

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('rsm_service_cases.case_id'),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    approver: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    decision_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    requested_event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    decision_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SlaPolicyCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    response_minutes: int = Field(ge=1, le=100_000)
    resolution_minutes: int = Field(ge=1, le=1_000_000)
    active: bool = True


class CaseSlaApplyRequest(BaseModel):
    policy_id: str
    event_id: UUID


class CaseAssignmentRequest(BaseModel):
    assignment_group: str = Field(min_length=1, max_length=200)
    assignee: str | None = Field(default=None, max_length=200)
    event_id: UUID


class ApprovalRequestCreate(BaseModel):
    approver: str = Field(min_length=1, max_length=200)
    event_id: UUID


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalStatus
    event_id: UUID
    reason: str | None = Field(default=None, max_length=1000)


def _aware(value: datetime | None) -> datetime | None:
    """PostgreSQL devolve tz-aware; SQLite devolve naive. Normaliza para UTC."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _case(db: Session, case_id: str) -> ServiceCaseRecord:
    record = db.get(ServiceCaseRecord, case_id)
    if record is None:
        raise ServiceCaseNotFoundError('ServiceCase não encontrado')
    return record


def _domain_policy(record: SlaPolicyRecord) -> SlaPolicy:
    return SlaPolicy(
        policy_id=record.policy_id,
        name=record.name,
        response_minutes=record.response_minutes,
        resolution_minutes=record.resolution_minutes,
        active=bool(record.active),
    )


def _event_exists(db: Session, event_id: str, *, expected_type: str, case_id: str) -> bool:
    """Replay: o mesmo event_id só é aceito para o mesmo efeito e o mesmo caso."""
    existing = db.get(ServiceCaseEventRecord, event_id)
    if existing is None:
        return False
    if existing.case_id != case_id or existing.event_type != expected_type:
        raise ServiceCaseConflictError('event_id já utilizado por outro efeito')
    return True


def _append_event(
    db: Session,
    *,
    event_id: str,
    case_id: str,
    event_type: str,
    correlation_id: str,
) -> None:
    db.add(
        ServiceCaseEventRecord(
            event_id=event_id,
            case_id=case_id,
            event_type=event_type,
            from_state=None,
            to_state=None,
            correlation_id=correlation_id,
        )
    )


def _current_assignment(db: Session, case_id: str) -> CaseAssignmentRecord | None:
    return (
        db.query(CaseAssignmentRecord)
        .filter(CaseAssignmentRecord.case_id == case_id)
        .order_by(CaseAssignmentRecord.sequence.desc())
        .first()
    )


def _approval_statuses(db: Session, case_id: str) -> tuple[ApprovalStatus, ...]:
    rows = (
        db.query(CaseApprovalRecord.status)
        .filter(CaseApprovalRecord.case_id == case_id)
        .all()
    )
    return tuple(ApprovalStatus(row[0]) for row in rows)


def _approval_transition_guard(
    db: Session,
    record: ServiceCaseRecord,
    target: ServiceCaseState,
) -> None:
    """Portão fail-closed: PENDING_APPROVAL -> IN_PROGRESS exige APPROVED."""
    from_state = ServiceCaseState(record.state)
    if not requires_approval(from_state, target):
        return
    try:
        assert_approval_allows_transition(from_state, target, _approval_statuses(db, record.case_id))
    except ApprovalRequiredError as exc:
        raise ServiceCaseConflictError(str(exc)) from exc


register_transition_guard(_approval_transition_guard)


def _sla_marks(db: Session, case_id: str) -> tuple[datetime | None, datetime | None]:
    """Deriva os marcos de SLA do histórico append-only, sem gravação paralela."""
    rows = (
        db.query(ServiceCaseEventRecord.to_state, ServiceCaseEventRecord.created_at)
        .filter(
            ServiceCaseEventRecord.case_id == case_id,
            ServiceCaseEventRecord.to_state.in_(
                [ServiceCaseState.IN_PROGRESS.value, ServiceCaseState.RESOLVED.value]
            ),
        )
        .order_by(ServiceCaseEventRecord.created_at)
        .all()
    )
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    for to_state, created_at in rows:
        moment = _aware(created_at)
        if to_state == ServiceCaseState.IN_PROGRESS.value and first_response_at is None:
            first_response_at = moment
        if to_state == ServiceCaseState.RESOLVED.value and resolved_at is None:
            resolved_at = moment
    return first_response_at, resolved_at


def _serialize_policy(record: SlaPolicyRecord) -> dict:
    return {
        'policy_id': record.policy_id,
        'code': record.code,
        'name': record.name,
        'response_minutes': record.response_minutes,
        'resolution_minutes': record.resolution_minutes,
        'active': bool(record.active),
    }


def _serialize_assignment(record: CaseAssignmentRecord) -> dict:
    return {
        'assignment_id': record.assignment_id,
        'sequence': record.sequence,
        'assignment_group': record.assignment_group,
        'assignee': record.assignee,
        'previous_group': record.previous_group,
        'previous_assignee': record.previous_assignee,
        'event_id': record.event_id,
        'correlation_id': record.correlation_id,
        'created_at': _aware(record.created_at).isoformat() if record.created_at else None,
    }


def _serialize_approval(record: CaseApprovalRecord) -> dict:
    return {
        'approval_id': record.approval_id,
        'sequence': record.sequence,
        'approver': record.approver,
        'status': record.status,
        'decision_reason': record.decision_reason,
        'correlation_id': record.correlation_id,
        'requested_at': _aware(record.requested_at).isoformat() if record.requested_at else None,
        'decided_at': _aware(record.decided_at).isoformat() if record.decided_at else None,
    }


def _serialize_sla(record: CaseSlaRecord) -> dict:
    return {
        'policy_id': record.policy_id,
        'priority': record.priority,
        'started_at': _aware(record.started_at).isoformat(),
        'response_due_at': _aware(record.response_due_at).isoformat(),
        'resolution_due_at': _aware(record.resolution_due_at).isoformat(),
        'schema_version': record.schema_version,
    }


def register_sla_policy(
    db: Session,
    payload: SlaPolicyCreateRequest,
    *,
    correlation_id: str,
) -> tuple[SlaPolicyRecord, bool]:
    code = payload.code.strip().upper()
    if payload.resolution_minutes < payload.response_minutes:
        raise SlaViolationError('resolution_minutes não pode ser menor que response_minutes')
    existing = db.query(SlaPolicyRecord).filter(SlaPolicyRecord.code == code).first()
    if existing is not None:
        return existing, True
    record = SlaPolicyRecord(
        policy_id=str(uuid4()),
        code=code,
        name=payload.name.strip(),
        response_minutes=payload.response_minutes,
        resolution_minutes=payload.resolution_minutes,
        active=payload.active,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(SlaPolicyRecord).filter(SlaPolicyRecord.code == code).first()
        if existing is not None:
            return existing, True
        raise ServiceCaseConflictError('política de SLA já registrada') from exc
    db.refresh(record)
    logger.info(
        'rsm_sla_policy_registered policy_id=%s code=%s correlation_id=%s',
        _safe_log_value(record.policy_id),
        _safe_log_value(record.code),
        _safe_log_value(correlation_id),
    )
    return record, False


def apply_case_sla(
    db: Session,
    case_id: str,
    payload: CaseSlaApplyRequest,
    *,
    correlation_id: str,
) -> tuple[CaseSlaRecord, bool]:
    case = _case(db, case_id)
    if _event_exists(db, str(payload.event_id), expected_type=EVENT_SLA_APPLIED, case_id=case_id):
        existing = db.get(CaseSlaRecord, case_id)
        if existing is None:
            raise ServiceCaseConflictError('evento de SLA registrado sem prazo persistido')
        return existing, True

    # A existência da política é verificada antes do estado do caso: uma política
    # inexistente é 404 independentemente de o caso já possuir SLA aplicado.
    policy_record = db.get(SlaPolicyRecord, payload.policy_id)
    if policy_record is None:
        raise ServiceCaseNotFoundError('política de SLA não encontrada')

    existing = db.get(CaseSlaRecord, case_id)
    if existing is not None:
        if existing.policy_id != payload.policy_id:
            raise ServiceCaseConflictError('caso já possui política de SLA divergente aplicada')
        return existing, True

    targets = calculate_sla_targets(
        _domain_policy(policy_record),
        ServiceCasePriority(case.priority),
        _aware(case.created_at),
    )
    record = CaseSlaRecord(
        case_id=case_id,
        policy_id=targets.policy_id,
        priority=targets.priority.value,
        started_at=targets.started_at,
        response_due_at=targets.response_due_at,
        resolution_due_at=targets.resolution_due_at,
        correlation_id=correlation_id,
    )
    db.add(record)
    _append_event(
        db,
        event_id=str(payload.event_id),
        case_id=case_id,
        event_type=EVENT_SLA_APPLIED,
        correlation_id=correlation_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        persisted = db.get(CaseSlaRecord, case_id)
        if persisted is not None:
            return persisted, True
        raise ServiceCaseConflictError('SLA já aplicado para este caso') from exc
    db.refresh(record)
    logger.info(
        'rsm_sla_applied case_id=%s policy_id=%s priority=%s correlation_id=%s',
        _safe_log_value(case_id),
        _safe_log_value(record.policy_id),
        _safe_log_value(record.priority),
        _safe_log_value(correlation_id),
    )
    return record, False


def change_assignment(
    db: Session,
    case_id: str,
    payload: CaseAssignmentRequest,
    *,
    correlation_id: str,
) -> tuple[CaseAssignmentRecord, bool]:
    _case(db, case_id)
    if _event_exists(db, str(payload.event_id), expected_type=EVENT_ASSIGNMENT_CHANGED, case_id=case_id):
        existing = (
            db.query(CaseAssignmentRecord)
            .filter(CaseAssignmentRecord.event_id == str(payload.event_id))
            .first()
        )
        if existing is None:
            raise ServiceCaseConflictError('evento de atribuição registrado sem histórico')
        return existing, True

    current = _current_assignment(db, case_id)
    change = plan_assignment(
        case_id=case_id,
        assignment_group=payload.assignment_group,
        assignee=payload.assignee,
        current_group=current.assignment_group if current else None,
        current_assignee=current.assignee if current else None,
        correlation_id=correlation_id,
    )
    if change.is_noop and current is not None:
        logger.info(
            'rsm_assignment_unchanged case_id=%s correlation_id=%s',
            _safe_log_value(case_id),
            _safe_log_value(correlation_id),
        )
        return current, True

    record = CaseAssignmentRecord(
        assignment_id=str(uuid4()),
        case_id=case_id,
        sequence=(current.sequence + 1) if current else 1,
        assignment_group=change.assignment_group,
        assignee=change.assignee,
        previous_group=change.previous_group,
        previous_assignee=change.previous_assignee,
        event_id=str(payload.event_id),
        correlation_id=correlation_id,
    )
    db.add(record)
    _append_event(
        db,
        event_id=str(payload.event_id),
        case_id=case_id,
        event_type=EVENT_ASSIGNMENT_CHANGED,
        correlation_id=correlation_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceCaseConflictError('atribuição concorrente detectada') from exc
    db.refresh(record)
    logger.info(
        'rsm_assignment_changed case_id=%s sequence=%s correlation_id=%s',
        _safe_log_value(case_id),
        record.sequence,
        _safe_log_value(correlation_id),
    )
    return record, False


def request_approval(
    db: Session,
    case_id: str,
    payload: ApprovalRequestCreate,
    *,
    correlation_id: str,
) -> tuple[CaseApprovalRecord, bool]:
    _case(db, case_id)
    if _event_exists(db, str(payload.event_id), expected_type=EVENT_APPROVAL_REQUESTED, case_id=case_id):
        existing = (
            db.query(CaseApprovalRecord)
            .filter(CaseApprovalRecord.requested_event_id == str(payload.event_id))
            .first()
        )
        if existing is None:
            raise ServiceCaseConflictError('evento de aprovação registrado sem histórico')
        return existing, True

    last = (
        db.query(CaseApprovalRecord)
        .filter(CaseApprovalRecord.case_id == case_id)
        .order_by(CaseApprovalRecord.sequence.desc())
        .first()
    )
    record = CaseApprovalRecord(
        approval_id=str(uuid4()),
        case_id=case_id,
        sequence=(last.sequence + 1) if last else 1,
        approver=payload.approver.strip(),
        status=ApprovalStatus.PENDING.value,
        requested_event_id=str(payload.event_id),
        correlation_id=correlation_id,
    )
    db.add(record)
    _append_event(
        db,
        event_id=str(payload.event_id),
        case_id=case_id,
        event_type=EVENT_APPROVAL_REQUESTED,
        correlation_id=correlation_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceCaseConflictError('aprovação já solicitada com este event_id') from exc
    db.refresh(record)
    logger.info(
        'rsm_approval_requested case_id=%s approval_id=%s correlation_id=%s',
        _safe_log_value(case_id),
        _safe_log_value(record.approval_id),
        _safe_log_value(correlation_id),
    )
    return record, False


def decide_approval(
    db: Session,
    case_id: str,
    approval_id: str,
    payload: ApprovalDecisionRequest,
    *,
    correlation_id: str,
) -> tuple[CaseApprovalRecord, bool]:
    _case(db, case_id)
    record = db.get(CaseApprovalRecord, approval_id)
    if record is None or record.case_id != case_id:
        raise ServiceCaseNotFoundError('aprovação não encontrada para o caso')

    if _event_exists(db, str(payload.event_id), expected_type=EVENT_APPROVAL_DECIDED, case_id=case_id):
        if record.decision_event_id != str(payload.event_id):
            raise ServiceCaseConflictError('event_id já utilizado por outra decisão')
        return record, True

    validate_approval_decision(ApprovalStatus(record.status), payload.decision)

    record.status = payload.decision.value
    record.decision_reason = (payload.reason or '').strip() or None
    record.decision_event_id = str(payload.event_id)
    record.decided_at = datetime.now(timezone.utc)
    _append_event(
        db,
        event_id=str(payload.event_id),
        case_id=case_id,
        event_type=EVENT_APPROVAL_DECIDED,
        correlation_id=correlation_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ServiceCaseConflictError('decisão concorrente detectada') from exc
    db.refresh(record)
    logger.info(
        'rsm_approval_decided case_id=%s approval_id=%s status=%s correlation_id=%s',
        _safe_log_value(case_id),
        _safe_log_value(record.approval_id),
        _safe_log_value(record.status),
        _safe_log_value(correlation_id),
    )
    return record, False


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, ServiceCaseNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if isinstance(exc, ServiceCaseConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if isinstance(
        exc,
        (SlaViolationError, AssignmentValidationError, ServiceManagementValidationError),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from None
    raise exc


@router.post('/v1/sla-policies')
def create_sla_policy(
    payload: SlaPolicyCreateRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = register_sla_policy(db, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'policy': _serialize_policy(record), 'duplicate': duplicate}, correlation_id)


@router.get('/v1/sla-policies')
def list_sla_policies(
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    records = db.query(SlaPolicyRecord).order_by(SlaPolicyRecord.code).all()
    return ok({'policies': [_serialize_policy(record) for record in records]})


@router.post('/v1/service-cases/{case_id}/sla')
def apply_sla(
    case_id: str,
    payload: CaseSlaApplyRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = apply_case_sla(db, case_id, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'sla': _serialize_sla(record), 'duplicate': duplicate}, correlation_id)


@router.post('/v1/service-cases/{case_id}/assignments')
def assign_case(
    case_id: str,
    payload: CaseAssignmentRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = change_assignment(db, case_id, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'assignment': _serialize_assignment(record), 'duplicate': duplicate}, correlation_id)


@router.post('/v1/service-cases/{case_id}/approvals')
def create_approval(
    case_id: str,
    payload: ApprovalRequestCreate,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = request_approval(db, case_id, payload, correlation_id=correlation_id)
    except Exception as exc:
        _raise_http(exc)
    return ok({'approval': _serialize_approval(record), 'duplicate': duplicate}, correlation_id)


@router.post('/v1/service-cases/{case_id}/approvals/{approval_id}/decision')
def decide_case_approval(
    case_id: str,
    approval_id: str,
    payload: ApprovalDecisionRequest,
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, None)
    try:
        record, duplicate = decide_approval(
            db,
            case_id,
            approval_id,
            payload,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        _raise_http(exc)
    return ok({'approval': _serialize_approval(record), 'duplicate': duplicate}, correlation_id)


@router.get('/v1/service-cases/{case_id}/operations')
def read_case_operations(
    case_id: str,
    evaluated_at: datetime | None = Query(default=None),
    _ctx: ServiceAuthContext = Depends(require_service_case_auth),
    db: Session = Depends(get_db),
):
    case = db.get(ServiceCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail='ServiceCase não encontrado')

    sla_record = db.get(CaseSlaRecord, case_id)
    sla_payload: dict | None = None
    if sla_record is not None:
        first_response_at, resolved_at = _sla_marks(db, case_id)
        moment = _aware(evaluated_at) or datetime.now(timezone.utc)
        # Os prazos persistidos na aplicação da política são a autoridade; a
        # avaliação nunca os recalcula, para não depender do relógio de leitura.
        try:
            targets = SlaTargets(
                policy_id=sla_record.policy_id,
                priority=ServiceCasePriority(sla_record.priority),
                started_at=_aware(sla_record.started_at),
                response_due_at=_aware(sla_record.response_due_at),
                resolution_due_at=_aware(sla_record.resolution_due_at),
            )
            state = evaluate_sla(
                targets,
                evaluated_at=moment,
                first_response_at=first_response_at,
                resolved_at=resolved_at,
            )
        except SlaViolationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        sla_payload = {
            **_serialize_sla(sla_record),
            'evaluated_at': moment.isoformat(),
            'first_response_at': first_response_at.isoformat() if first_response_at else None,
            'resolved_at': resolved_at.isoformat() if resolved_at else None,
            'state': state.value,
        }

    assignments = (
        db.query(CaseAssignmentRecord)
        .filter(CaseAssignmentRecord.case_id == case_id)
        .order_by(CaseAssignmentRecord.sequence)
        .all()
    )
    approvals = (
        db.query(CaseApprovalRecord)
        .filter(CaseApprovalRecord.case_id == case_id)
        .order_by(CaseApprovalRecord.sequence)
        .all()
    )
    events = (
        db.query(ServiceCaseEventRecord)
        .filter(ServiceCaseEventRecord.case_id == case_id)
        .order_by(ServiceCaseEventRecord.created_at, ServiceCaseEventRecord.event_id)
        .all()
    )
    current = assignments[-1] if assignments else None
    return ok(
        {
            'case_id': case_id,
            'state': case.state,
            'priority': case.priority,
            'version': case.version,
            'sla': sla_payload,
            'current_assignment': _serialize_assignment(current) if current else None,
            'assignment_history': [_serialize_assignment(item) for item in assignments],
            'approvals': [_serialize_approval(item) for item in approvals],
            'history': [
                {
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'from_state': event.from_state,
                    'to_state': event.to_state,
                    'correlation_id': event.correlation_id,
                }
                for event in events
            ],
        }
    )
