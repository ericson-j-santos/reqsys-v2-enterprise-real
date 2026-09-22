import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.service_management import (
    Approval,
    ApprovalStatus,
    CaseEvent,
    ChangeCiEvidence,
    ChangeTraceability,
    EvidenceReference,
    ExternalReference,
    ExternalReferenceType,
    Impact,
    InvalidStateTransition,
    Service,
    ServiceCase,
    ServiceCasePriority,
    ServiceCaseState,
    ServiceCaseType,
    ServiceDependency,
    ServiceDependencyType,
    ServiceManagementValidationError,
    ServiceOffering,
    SlaPolicy,
    Urgency,
    calculate_priority,
    validate_change_ci,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _case(*, key: str = 'rsm-1783') -> ServiceCase:
    return ServiceCase.create(
        case_type=ServiceCaseType.REQUEST,
        service_id=str(uuid4()),
        requester='qa-rsm',
        impact=Impact.HIGH,
        urgency=Urgency.CRITICAL,
        correlation_id='corr-rsm-1783',
        idempotency_key=_sha(key),
    )


def _change_case(*, key: str = 'rsm-1789') -> ServiceCase:
    return ServiceCase.create(
        case_type=ServiceCaseType.CHANGE,
        service_id=str(uuid4()),
        requester='qa-rsm-change',
        impact=Impact.HIGH,
        urgency=Urgency.HIGH,
        correlation_id='corr-rsm-1789',
        idempotency_key=_sha(key),
    )


def _change_traceability(head_sha: str) -> ChangeTraceability:
    return ChangeTraceability(
        requirement=ExternalReference(ExternalReferenceType.REQUIREMENT, 'REQ-1789'),
        sdd=ExternalReference(ExternalReferenceType.SDD, 'rsm-07-change-traceability'),
        pull_request=ExternalReference(ExternalReferenceType.PULL_REQUEST, 'PR-1789-test'),
        head_sha=head_sha,
    )


@pytest.mark.parametrize(
    ('impact', 'urgency', 'expected'),
    [
        (Impact.CRITICAL, Urgency.HIGH, ServiceCasePriority.P1),
        (Impact.HIGH, Urgency.MEDIUM, ServiceCasePriority.P2),
        (Impact.MEDIUM, Urgency.LOW, ServiceCasePriority.P3),
        (Impact.LOW, Urgency.LOW, ServiceCasePriority.P4),
    ],
)
def test_priority_matrix_is_deterministic(impact, urgency, expected):
    assert calculate_priority(impact, urgency) is expected


def test_service_case_contract_normalizes_identity_and_replay_key():
    service_id = str(uuid4())
    key = _sha('same-logical-request')

    first = ServiceCase.create(
        case_type=ServiceCaseType.REQUEST,
        service_id=service_id,
        requester=' solicitante ',
        impact=Impact.HIGH,
        urgency=Urgency.CRITICAL,
        correlation_id=' corr-1 ',
        idempotency_key=key,
    )
    replay = ServiceCase.create(
        case_type=ServiceCaseType.REQUEST,
        service_id=service_id,
        requester='solicitante',
        impact=Impact.HIGH,
        urgency=Urgency.CRITICAL,
        correlation_id='corr-2',
        idempotency_key=key,
    )

    assert first.priority is ServiceCasePriority.P1
    assert first.requester == 'solicitante'
    assert first.correlation_id == 'corr-1'
    assert first.case_id != replay.case_id
    assert first.logical_identity == replay.logical_identity == key


def test_contract_harness_accepts_valid_path_and_rejects_terminal_reopen():
    original = _case()
    closed = (
        original.transition_to(ServiceCaseState.TRIAGE)
        .transition_to(ServiceCaseState.IN_PROGRESS)
        .transition_to(ServiceCaseState.RESOLVED)
        .transition_to(ServiceCaseState.CLOSED)
    )

    assert original.state is ServiceCaseState.NEW
    assert closed.state is ServiceCaseState.CLOSED
    with pytest.raises(InvalidStateTransition, match='CLOSED -> IN_PROGRESS'):
        closed.transition_to(ServiceCaseState.IN_PROGRESS)
    assert closed.state is ServiceCaseState.CLOSED


def test_invalid_idempotency_key_is_rejected():
    with pytest.raises(ServiceManagementValidationError, match='idempotency_key'):
        ServiceCase.create(
            case_type=ServiceCaseType.INCIDENT,
            service_id=str(uuid4()),
            requester='ops',
            impact=Impact.MEDIUM,
            urgency=Urgency.MEDIUM,
            correlation_id='corr-invalid',
            idempotency_key='not-a-sha256',
        )


def test_minimal_supporting_contracts_preserve_service_reference_model():
    service = Service(str(uuid4()), 'reqsys_core', 'ReqSys Core')
    offering = ServiceOffering(str(uuid4()), service.service_id, 'REQUEST_STANDARD', 'Solicitação padrão')
    policy = SlaPolicy(str(uuid4()), 'Padrão', response_minutes=30, resolution_minutes=240)
    dependency = ServiceDependency(service.service_id, str(uuid4()), ServiceDependencyType.DEPENDS_ON)

    assert service.code == 'REQSYS_CORE'
    assert offering.service_id == service.service_id
    assert policy.resolution_minutes == 240
    assert dependency.source_service_id == service.service_id


def test_approval_and_event_require_auditable_timestamps():
    approval = Approval(
        approval_id=str(uuid4()),
        approver='gestor',
        status=ApprovalStatus.APPROVED,
        correlation_id='corr-approval',
        decided_at=datetime.now(timezone.utc),
    )
    event = CaseEvent(
        event_id=str(uuid4()),
        case_id=str(uuid4()),
        event_type='CASE_CREATED',
        correlation_id='corr-event',
    )

    assert approval.status is ApprovalStatus.APPROVED
    assert event.occurred_at.tzinfo is not None

    with pytest.raises(ServiceManagementValidationError, match='decided_at'):
        Approval(
            approval_id=str(uuid4()),
            approver='gestor',
            status=ApprovalStatus.REJECTED,
            correlation_id='corr-rejected',
        )


def test_evidence_digest_and_self_dependency_controls_fail_closed():
    with pytest.raises(ServiceManagementValidationError, match='sha256'):
        EvidenceReference('ev-1', 'test', 'urn:rsm:test', sha256='ABC')

    service_id = str(uuid4())
    with pytest.raises(ServiceManagementValidationError, match='si mesma'):
        ServiceDependency(service_id, service_id, ServiceDependencyType.CALLS)



def test_change_accepts_requirement_sdd_pr_and_ci_for_exact_sha():
    head_sha = 'a' * 40
    case = _change_case()
    traceability = _change_traceability(head_sha)
    evidence = ChangeCiEvidence(head_sha=head_sha, run_id='run-1789-ok', conclusion='success')

    validate_change_ci(case, traceability, evidence)

    assert traceability.requirement.external_id == 'REQ-1789'
    assert traceability.sdd.external_id == 'rsm-07-change-traceability'
    assert traceability.pull_request.external_id == 'PR-1789-test'
    assert case.state is ServiceCaseState.NEW


def test_change_rejects_green_ci_from_different_sha():
    case = _change_case(key='rsm-1789-sha-mismatch')
    traceability = _change_traceability('a' * 40)
    evidence = ChangeCiEvidence(head_sha='b' * 40, run_id='run-1789-wrong-sha', conclusion='success')

    with pytest.raises(ServiceManagementValidationError, match='outro SHA'):
        validate_change_ci(case, traceability, evidence)

    assert case.state is ServiceCaseState.NEW
    with pytest.raises(ServiceManagementValidationError, match='SHA completo'):
        ChangeCiEvidence(head_sha='a' * 12, run_id='run-short-sha', conclusion='success')


def test_change_blocks_when_ci_evidence_is_missing():
    case = _change_case(key='rsm-1789-missing-evidence')
    traceability = _change_traceability('c' * 40)

    with pytest.raises(ServiceManagementValidationError, match='obrigatória'):
        validate_change_ci(case, traceability, None)

    assert case.state is ServiceCaseState.NEW


def test_change_traceability_cannot_be_applied_to_non_change_case():
    case = _case(key='rsm-1789-not-change')
    traceability = _change_traceability('d' * 40)
    evidence = ChangeCiEvidence(head_sha='d' * 40, run_id='run-1789-request', conclusion='success')

    with pytest.raises(ServiceManagementValidationError, match='somente case_type CHANGE'):
        validate_change_ci(case, traceability, evidence)

    assert case.state is ServiceCaseState.NEW
