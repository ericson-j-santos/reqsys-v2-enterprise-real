"""Núcleo de domínio do ReqSys Service Management (RSM).

O módulo é intencionalmente independente de FastAPI, SQLAlchemy, GitHub e Teams.
Persistência e integrações entram por adaptadores nos incrementos seguintes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

SCHEMA_VERSION = '1.0.0'
SHA256_RE = re.compile(r'^[a-f0-9]{64}$')
SERVICE_CODE_RE = re.compile(r'^[A-Z0-9][A-Z0-9_-]+$')


class ServiceManagementValidationError(ValueError):
    """Violação de uma invariante do domínio RSM."""


class InvalidStateTransition(ServiceManagementValidationError):
    """Transição de estado não permitida."""


class ServiceCaseType(str, Enum):
    REQUEST = 'REQUEST'
    INCIDENT = 'INCIDENT'
    PROBLEM = 'PROBLEM'
    CHANGE = 'CHANGE'


class ServiceCaseState(str, Enum):
    NEW = 'NEW'
    TRIAGE = 'TRIAGE'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    IN_PROGRESS = 'IN_PROGRESS'
    PENDING_EXTERNAL = 'PENDING_EXTERNAL'
    RESOLVED = 'RESOLVED'
    CLOSED = 'CLOSED'
    CANCELED = 'CANCELED'


class Impact(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class Urgency(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class ServiceCasePriority(str, Enum):
    P1 = 'P1'
    P2 = 'P2'
    P3 = 'P3'
    P4 = 'P4'


class ApprovalStatus(str, Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'


class ExternalReferenceType(str, Enum):
    REQUIREMENT = 'REQUIREMENT'
    PULL_REQUEST = 'PULL_REQUEST'
    WORKFLOW_RUN = 'WORKFLOW_RUN'
    DEPLOYMENT = 'DEPLOYMENT'
    SERVICE_CASE = 'SERVICE_CASE'


class ServiceDependencyType(str, Enum):
    DEPENDS_ON = 'DEPENDS_ON'
    CALLS = 'CALLS'
    STORES_IN = 'STORES_IN'
    RUNS_ON = 'RUNS_ON'


_IMPACT_WEIGHT = {
    Impact.LOW: 1,
    Impact.MEDIUM: 2,
    Impact.HIGH: 3,
    Impact.CRITICAL: 4,
}
_URGENCY_WEIGHT = {
    Urgency.LOW: 1,
    Urgency.MEDIUM: 2,
    Urgency.HIGH: 3,
    Urgency.CRITICAL: 4,
}
_ALLOWED_TRANSITIONS = {
    ServiceCaseState.NEW: frozenset({ServiceCaseState.TRIAGE, ServiceCaseState.CANCELED}),
    ServiceCaseState.TRIAGE: frozenset(
        {ServiceCaseState.PENDING_APPROVAL, ServiceCaseState.IN_PROGRESS, ServiceCaseState.CANCELED}
    ),
    ServiceCaseState.PENDING_APPROVAL: frozenset(
        {ServiceCaseState.TRIAGE, ServiceCaseState.IN_PROGRESS, ServiceCaseState.CANCELED}
    ),
    ServiceCaseState.IN_PROGRESS: frozenset(
        {ServiceCaseState.PENDING_EXTERNAL, ServiceCaseState.RESOLVED, ServiceCaseState.CANCELED}
    ),
    ServiceCaseState.PENDING_EXTERNAL: frozenset(
        {ServiceCaseState.IN_PROGRESS, ServiceCaseState.RESOLVED, ServiceCaseState.CANCELED}
    ),
    ServiceCaseState.RESOLVED: frozenset({ServiceCaseState.IN_PROGRESS, ServiceCaseState.CLOSED}),
    ServiceCaseState.CLOSED: frozenset(),
    ServiceCaseState.CANCELED: frozenset(),
}


def _text(value: str, field_name: str, *, max_length: int = 200) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ServiceManagementValidationError(f'{field_name} deve ser informado')
    if len(normalized) > max_length:
        raise ServiceManagementValidationError(f'{field_name} excede {max_length} caracteres')
    return normalized


def _uuid(value: str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ServiceManagementValidationError(f'{field_name} deve ser UUID válido') from exc


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ServiceManagementValidationError(f'{field_name} deve possuir timezone')
    return value


def calculate_priority(impact: Impact, urgency: Urgency) -> ServiceCasePriority:
    if not isinstance(impact, Impact) or not isinstance(urgency, Urgency):
        raise ServiceManagementValidationError('impact e urgency devem usar os enums do contrato')
    score = _IMPACT_WEIGHT[impact] + _URGENCY_WEIGHT[urgency]
    if score >= 7:
        return ServiceCasePriority.P1
    if score >= 5:
        return ServiceCasePriority.P2
    if score >= 3:
        return ServiceCasePriority.P3
    return ServiceCasePriority.P4


@dataclass(frozen=True, slots=True)
class Service:
    """Visão de domínio do catálogo; persistência canônica atual é ServicoTI."""

    service_id: str
    code: str
    name: str
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, 'service_id', _uuid(self.service_id, 'service_id'))
        code = _text(self.code, 'code', max_length=80).upper()
        if not SERVICE_CODE_RE.fullmatch(code):
            raise ServiceManagementValidationError('code possui formato inválido')
        object.__setattr__(self, 'code', code)
        object.__setattr__(self, 'name', _text(self.name, 'name'))


@dataclass(frozen=True, slots=True)
class ServiceOffering:
    offering_id: str
    service_id: str
    code: str
    name: str
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, 'offering_id', _uuid(self.offering_id, 'offering_id'))
        object.__setattr__(self, 'service_id', _uuid(self.service_id, 'service_id'))
        code = _text(self.code, 'code', max_length=80).upper()
        if not SERVICE_CODE_RE.fullmatch(code):
            raise ServiceManagementValidationError('code possui formato inválido')
        object.__setattr__(self, 'code', code)
        object.__setattr__(self, 'name', _text(self.name, 'name'))


@dataclass(frozen=True, slots=True)
class SlaPolicy:
    policy_id: str
    name: str
    response_minutes: int
    resolution_minutes: int
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, 'policy_id', _uuid(self.policy_id, 'policy_id'))
        object.__setattr__(self, 'name', _text(self.name, 'name'))
        if self.response_minutes <= 0:
            raise ServiceManagementValidationError('response_minutes deve ser positivo')
        if self.resolution_minutes < self.response_minutes:
            raise ServiceManagementValidationError('resolution_minutes não pode ser menor que response_minutes')


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    approver: str
    status: ApprovalStatus
    correlation_id: str
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'approval_id', _uuid(self.approval_id, 'approval_id'))
        object.__setattr__(self, 'approver', _text(self.approver, 'approver'))
        object.__setattr__(self, 'correlation_id', _text(self.correlation_id, 'correlation_id', max_length=120))
        if not isinstance(self.status, ApprovalStatus):
            raise ServiceManagementValidationError('status de aprovação inválido')
        if self.status is ApprovalStatus.PENDING and self.decided_at is not None:
            raise ServiceManagementValidationError('aprovação pendente não pode possuir decided_at')
        if self.status is not ApprovalStatus.PENDING and self.decided_at is None:
            raise ServiceManagementValidationError('aprovação decidida exige decided_at')
        if self.decided_at is not None:
            _aware(self.decided_at, 'decided_at')


@dataclass(frozen=True, slots=True)
class ExternalReference:
    kind: ExternalReferenceType
    external_id: str
    url: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ExternalReferenceType):
            raise ServiceManagementValidationError('kind de referência externa inválido')
        object.__setattr__(self, 'external_id', _text(self.external_id, 'external_id'))
        if self.url is not None:
            object.__setattr__(self, 'url', _text(self.url, 'url', max_length=1000))


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    evidence_id: str
    kind: str
    uri: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'evidence_id', _text(self.evidence_id, 'evidence_id'))
        object.__setattr__(self, 'kind', _text(self.kind, 'kind', max_length=80))
        object.__setattr__(self, 'uri', _text(self.uri, 'uri', max_length=1000))
        if self.sha256 is not None and not SHA256_RE.fullmatch(self.sha256):
            raise ServiceManagementValidationError('sha256 de evidência deve ser hexadecimal minúsculo com 64 caracteres')


@dataclass(frozen=True, slots=True)
class CaseEvent:
    event_id: str
    case_id: str
    event_type: str
    correlation_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, 'event_id', _uuid(self.event_id, 'event_id'))
        object.__setattr__(self, 'case_id', _uuid(self.case_id, 'case_id'))
        object.__setattr__(self, 'event_type', _text(self.event_type, 'event_type', max_length=80))
        object.__setattr__(self, 'correlation_id', _text(self.correlation_id, 'correlation_id', max_length=120))
        _aware(self.occurred_at, 'occurred_at')
        if self.schema_version != SCHEMA_VERSION:
            raise ServiceManagementValidationError(f'schema_version deve ser {SCHEMA_VERSION}')


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    source_service_id: str
    target_service_id: str
    kind: ServiceDependencyType

    def __post_init__(self) -> None:
        source = _uuid(self.source_service_id, 'source_service_id')
        target = _uuid(self.target_service_id, 'target_service_id')
        if source == target:
            raise ServiceManagementValidationError('dependência de serviço não pode apontar para si mesma')
        if not isinstance(self.kind, ServiceDependencyType):
            raise ServiceManagementValidationError('kind de dependência inválido')
        object.__setattr__(self, 'source_service_id', source)
        object.__setattr__(self, 'target_service_id', target)


@dataclass(frozen=True, slots=True)
class ServiceCase:
    case_id: str
    case_type: ServiceCaseType
    service_id: str
    requester: str
    impact: Impact
    urgency: Urgency
    correlation_id: str
    idempotency_key: str
    state: ServiceCaseState = ServiceCaseState.NEW
    assignment_group: str | None = None
    assignee: str | None = None
    sla_policy_id: str | None = None
    approvals: tuple[Approval, ...] = ()
    references: tuple[ExternalReference, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    schema_version: str = SCHEMA_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: ServiceCasePriority = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'case_id', _uuid(self.case_id, 'case_id'))
        object.__setattr__(self, 'service_id', _uuid(self.service_id, 'service_id'))
        object.__setattr__(self, 'requester', _text(self.requester, 'requester'))
        object.__setattr__(self, 'correlation_id', _text(self.correlation_id, 'correlation_id', max_length=120))
        if not isinstance(self.case_type, ServiceCaseType):
            raise ServiceManagementValidationError('case_type inválido')
        if not isinstance(self.state, ServiceCaseState):
            raise ServiceManagementValidationError('state inválido')
        if not SHA256_RE.fullmatch(self.idempotency_key):
            raise ServiceManagementValidationError('idempotency_key deve ser SHA-256 hexadecimal minúsculo')
        if self.schema_version != SCHEMA_VERSION:
            raise ServiceManagementValidationError(f'schema_version deve ser {SCHEMA_VERSION}')
        _aware(self.created_at, 'created_at')
        if self.assignment_group is not None:
            object.__setattr__(self, 'assignment_group', _text(self.assignment_group, 'assignment_group'))
        if self.assignee is not None:
            object.__setattr__(self, 'assignee', _text(self.assignee, 'assignee'))
        if self.sla_policy_id is not None:
            object.__setattr__(self, 'sla_policy_id', _uuid(self.sla_policy_id, 'sla_policy_id'))
        object.__setattr__(self, 'approvals', tuple(self.approvals))
        object.__setattr__(self, 'references', tuple(self.references))
        object.__setattr__(self, 'evidence', tuple(self.evidence))
        object.__setattr__(self, 'priority', calculate_priority(self.impact, self.urgency))

    @classmethod
    def create(
        cls,
        *,
        case_type: ServiceCaseType,
        service_id: str,
        requester: str,
        impact: Impact,
        urgency: Urgency,
        correlation_id: str,
        idempotency_key: str,
    ) -> 'ServiceCase':
        return cls(
            case_id=str(uuid4()),
            case_type=case_type,
            service_id=service_id,
            requester=requester,
            impact=impact,
            urgency=urgency,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    @property
    def logical_identity(self) -> str:
        """Identidade estável usada pelo repositório futuro para deduplicação."""
        return self.idempotency_key

    def allowed_transitions(self) -> frozenset[ServiceCaseState]:
        return _ALLOWED_TRANSITIONS[self.state]

    def transition_to(self, target: ServiceCaseState) -> 'ServiceCase':
        if not isinstance(target, ServiceCaseState):
            raise ServiceManagementValidationError('target deve usar ServiceCaseState')
        if target not in self.allowed_transitions():
            raise InvalidStateTransition(f'transição não permitida: {self.state.value} -> {target.value}')
        return replace(self, state=target)
