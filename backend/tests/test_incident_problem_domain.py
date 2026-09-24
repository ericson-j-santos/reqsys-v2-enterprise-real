from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from app.domain.service_management import (
    EvidenceReference,
    Impact,
    IncidentProblemRelation,
    ProblemRootCause,
    ServiceCase,
    ServiceCaseType,
    ServiceManagementValidationError,
    Urgency,
    validate_incident_problem_relation,
    validate_problem_root_cause,
)


def _key(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _case(case_type: ServiceCaseType) -> ServiceCase:
    return ServiceCase.create(
        case_type=case_type,
        service_id=str(uuid4()),
        requester='rsm-08-test',
        impact=Impact.HIGH,
        urgency=Urgency.HIGH,
        correlation_id=f'rsm08-{uuid4().hex}',
        idempotency_key=_key(uuid4().hex),
    )


def test_incident_problem_relation_accepts_only_incident_to_problem():
    incident = _case(ServiceCaseType.INCIDENT)
    problem = _case(ServiceCaseType.PROBLEM)
    relation = IncidentProblemRelation(
        incident_case_id=incident.case_id,
        problem_case_id=problem.case_id,
        correlation_id='rsm08-domain',
    )

    validate_incident_problem_relation(incident, problem, relation)

    request = _case(ServiceCaseType.REQUEST)
    with pytest.raises(ServiceManagementValidationError, match='origem'):
        validate_incident_problem_relation(request, problem, relation)


def test_incident_problem_relation_rejects_wrong_target_and_self_reference():
    incident = _case(ServiceCaseType.INCIDENT)
    wrong_target = _case(ServiceCaseType.INCIDENT)
    relation = IncidentProblemRelation(
        incident_case_id=incident.case_id,
        problem_case_id=wrong_target.case_id,
        correlation_id='rsm08-wrong-target',
    )
    with pytest.raises(ServiceManagementValidationError, match='destino'):
        validate_incident_problem_relation(incident, wrong_target, relation)

    with pytest.raises(ServiceManagementValidationError, match='si mesmo'):
        IncidentProblemRelation(
            incident_case_id=incident.case_id,
            problem_case_id=incident.case_id,
            correlation_id='rsm08-self',
        )


def test_problem_root_cause_requires_problem_and_objective_evidence():
    problem = _case(ServiceCaseType.PROBLEM)
    evidence = EvidenceReference(
        evidence_id=str(uuid4()),
        kind='root-cause',
        uri='urn:reqsys:rsm08:rca',
        sha256=_key('root-cause-evidence'),
    )
    root_cause = ProblemRootCause(
        problem_case_id=problem.case_id,
        statement='Falha de configuração reproduzida e comprovada.',
        evidence=evidence,
        correlation_id='rsm08-rca',
    )
    validate_problem_root_cause(problem, root_cause)

    incident = _case(ServiceCaseType.INCIDENT)
    with pytest.raises(ServiceManagementValidationError, match='somente case_type PROBLEM'):
        validate_problem_root_cause(incident, root_cause)

    with pytest.raises(ServiceManagementValidationError, match='sha256'):
        EvidenceReference(
            evidence_id=str(uuid4()),
            kind='root-cause',
            uri='urn:reqsys:rsm08:bad',
            sha256='INVALID',
        )
