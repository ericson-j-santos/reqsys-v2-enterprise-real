"""Controles operacionais do ReqSys Service Management (RSM-04).

Cobre SLA determinístico, atribuição auditável e aprovação/rejeição fail-closed.
O módulo é puro: não depende de FastAPI, SQLAlchemy, GitHub ou Teams. Todo cálculo
é função total das entradas, sem leitura de relógio implícita — o instante de
avaliação é sempre recebido por parâmetro, para que o resultado seja reproduzível.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.domain.service_management import (
    ApprovalStatus,
    ServiceCasePriority,
    ServiceCaseState,
    ServiceManagementValidationError,
    SlaPolicy,
)

OPERATIONS_SCHEMA_VERSION = '1.0.0'

# Fator inteiro por prioridade: mantém o cálculo determinístico e sem ponto
# flutuante. P1 usa o prazo base da política; prioridades menores o multiplicam.
PRIORITY_SLA_FACTOR: dict[ServiceCasePriority, int] = {
    ServiceCasePriority.P1: 1,
    ServiceCasePriority.P2: 2,
    ServiceCasePriority.P3: 4,
    ServiceCasePriority.P4: 8,
}

# Estados a partir dos quais a decisão de aprovação ainda faz sentido.
APPROVAL_GATED_TRANSITIONS: frozenset[tuple[ServiceCaseState, ServiceCaseState]] = frozenset(
    {(ServiceCaseState.PENDING_APPROVAL, ServiceCaseState.IN_PROGRESS)}
)


class SlaState(str, Enum):
    ON_TIME = 'ON_TIME'
    RESPONSE_BREACHED = 'RESPONSE_BREACHED'
    RESOLUTION_BREACHED = 'RESOLUTION_BREACHED'


class SlaViolationError(ServiceManagementValidationError):
    """Entrada de SLA inconsistente ou instante de avaliação inválido."""


class ApprovalRequiredError(ServiceManagementValidationError):
    """Transição bloqueada por ausência de aprovação válida."""


class AssignmentValidationError(ServiceManagementValidationError):
    """Atribuição inválida de grupo/responsável."""


def _aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise SlaViolationError(f'{field_name} deve ser datetime')
    if value.tzinfo is None or value.utcoffset() is None:
        raise SlaViolationError(f'{field_name} deve possuir timezone')
    return value


def _actor(value: str | None, field_name: str, *, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise AssignmentValidationError(f'{field_name} deve ser informado')
        return None
    normalized = str(value).strip()
    if not normalized:
        if required:
            raise AssignmentValidationError(f'{field_name} deve ser informado')
        return None
    if len(normalized) > 200:
        raise AssignmentValidationError(f'{field_name} excede 200 caracteres')
    return normalized


@dataclass(frozen=True, slots=True)
class SlaTargets:
    """Prazos absolutos derivados da política, da prioridade e do início do caso."""

    policy_id: str
    priority: ServiceCasePriority
    started_at: datetime
    response_due_at: datetime
    resolution_due_at: datetime
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _aware(self.started_at, 'started_at')
        _aware(self.response_due_at, 'response_due_at')
        _aware(self.resolution_due_at, 'resolution_due_at')
        if self.response_due_at <= self.started_at:
            raise SlaViolationError('response_due_at deve ser posterior a started_at')
        if self.resolution_due_at < self.response_due_at:
            raise SlaViolationError('resolution_due_at não pode preceder response_due_at')
        if self.schema_version != OPERATIONS_SCHEMA_VERSION:
            raise SlaViolationError(f'schema_version deve ser {OPERATIONS_SCHEMA_VERSION}')


def calculate_sla_targets(
    policy: SlaPolicy,
    priority: ServiceCasePriority,
    started_at: datetime,
) -> SlaTargets:
    """Calcula prazos de SLA de forma determinística e reproduzível.

    Mesma política, mesma prioridade e mesmo `started_at` produzem sempre os
    mesmos prazos. Política inativa não produz prazo (fail-closed).
    """
    if not isinstance(policy, SlaPolicy):
        raise SlaViolationError('policy deve ser SlaPolicy')
    if not policy.active:
        raise SlaViolationError('política de SLA inativa não pode ser aplicada')
    if not isinstance(priority, ServiceCasePriority):
        raise SlaViolationError('priority deve usar ServiceCasePriority')
    _aware(started_at, 'started_at')

    factor = PRIORITY_SLA_FACTOR[priority]
    return SlaTargets(
        policy_id=policy.policy_id,
        priority=priority,
        started_at=started_at,
        response_due_at=started_at + timedelta(minutes=policy.response_minutes * factor),
        resolution_due_at=started_at + timedelta(minutes=policy.resolution_minutes * factor),
    )


def evaluate_sla(
    targets: SlaTargets,
    *,
    evaluated_at: datetime,
    first_response_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> SlaState:
    """Avalia o estado do SLA num instante explícito.

    O instante de avaliação nunca é lido do relógio interno: um `evaluated_at`
    anterior ao início do caso, ou marcos anteriores ao início, são rejeitados,
    de modo que manipulação de relógio não produz estado favorável silencioso.
    """
    if not isinstance(targets, SlaTargets):
        raise SlaViolationError('targets deve ser SlaTargets')
    _aware(evaluated_at, 'evaluated_at')
    if evaluated_at < targets.started_at:
        raise SlaViolationError('evaluated_at não pode preceder started_at')
    if first_response_at is not None:
        _aware(first_response_at, 'first_response_at')
        if first_response_at < targets.started_at:
            raise SlaViolationError('first_response_at não pode preceder started_at')
    if resolved_at is not None:
        _aware(resolved_at, 'resolved_at')
        if resolved_at < targets.started_at:
            raise SlaViolationError('resolved_at não pode preceder started_at')
        if first_response_at is not None and resolved_at < first_response_at:
            raise SlaViolationError('resolved_at não pode preceder first_response_at')

    resolution_reference = resolved_at if resolved_at is not None else evaluated_at
    if resolution_reference > targets.resolution_due_at:
        return SlaState.RESOLUTION_BREACHED

    response_reference = first_response_at if first_response_at is not None else evaluated_at
    if response_reference > targets.response_due_at:
        return SlaState.RESPONSE_BREACHED

    return SlaState.ON_TIME


@dataclass(frozen=True, slots=True)
class AssignmentChange:
    """Mudança de atribuição já normalizada, pronta para o histórico."""

    case_id: str
    assignment_group: str
    assignee: str | None
    previous_group: str | None
    previous_assignee: str | None
    correlation_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, 'assignment_group', _actor(self.assignment_group, 'assignment_group'))
        object.__setattr__(self, 'assignee', _actor(self.assignee, 'assignee', required=False))
        object.__setattr__(
            self, 'previous_group', _actor(self.previous_group, 'previous_group', required=False)
        )
        object.__setattr__(
            self, 'previous_assignee', _actor(self.previous_assignee, 'previous_assignee', required=False)
        )
        correlation_id = _actor(self.correlation_id, 'correlation_id')
        object.__setattr__(self, 'correlation_id', correlation_id)

    @property
    def is_noop(self) -> bool:
        """Reatribuição idêntica: não deve gerar novo registro de histórico."""
        return (
            self.assignment_group == self.previous_group
            and self.assignee == self.previous_assignee
        )


def plan_assignment(
    *,
    case_id: str,
    assignment_group: str,
    assignee: str | None,
    current_group: str | None,
    current_assignee: str | None,
    correlation_id: str,
) -> AssignmentChange:
    """Normaliza a atribuição pedida contra a atual, sem aplicar efeito."""
    return AssignmentChange(
        case_id=case_id,
        assignment_group=assignment_group,
        assignee=assignee,
        previous_group=current_group,
        previous_assignee=current_assignee,
        correlation_id=correlation_id,
    )


def requires_approval(from_state: ServiceCaseState, to_state: ServiceCaseState) -> bool:
    """Indica se a transição está sujeita ao portão de aprovação."""
    if not isinstance(from_state, ServiceCaseState) or not isinstance(to_state, ServiceCaseState):
        raise ServiceManagementValidationError('estados devem usar ServiceCaseState')
    return (from_state, to_state) in APPROVAL_GATED_TRANSITIONS


def assert_approval_allows_transition(
    from_state: ServiceCaseState,
    to_state: ServiceCaseState,
    approval_statuses: tuple[ApprovalStatus, ...],
) -> None:
    """Fail-closed: transição sob portão exige ao menos uma aprovação APPROVED.

    Ausência de aprovação, aprovação apenas PENDING ou apenas REJECTED bloqueiam
    a transição. A rejeição não é apagada: ela permanece no histórico e continua
    bloqueando enquanto não houver uma aprovação válida.
    """
    if not requires_approval(from_state, to_state):
        return
    for status in approval_statuses:
        if not isinstance(status, ApprovalStatus):
            raise ServiceManagementValidationError('status de aprovação inválido no histórico')
    if ApprovalStatus.APPROVED not in approval_statuses:
        raise ApprovalRequiredError(
            f'transição {from_state.value} -> {to_state.value} exige aprovação APPROVED'
        )


def validate_approval_decision(
    current: ApprovalStatus,
    decision: ApprovalStatus,
) -> None:
    """Decisão de aprovação é terminal: só PENDING pode ser decidida."""
    if not isinstance(current, ApprovalStatus) or not isinstance(decision, ApprovalStatus):
        raise ServiceManagementValidationError('status de aprovação inválido')
    if decision is ApprovalStatus.PENDING:
        raise ServiceManagementValidationError('decisão deve ser APPROVED ou REJECTED')
    if current is not ApprovalStatus.PENDING:
        raise ServiceManagementValidationError(
            f'aprovação já decidida como {current.value} não pode ser alterada'
        )
