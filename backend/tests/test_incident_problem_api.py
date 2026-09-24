from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.service_cases import (
    IncidentProblemLinkRecord,
    ProblemRootCauseRecord,
    ServiceCaseEventRecord,
    require_service_case_auth,
)
from app.core.service_tokens import ServiceAuthContext
from app.db import Base, get_db
from app.main import app
from app.models.gestao_ti import ServicoTI

engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _db_override():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def _auth_override():
    return ServiceAuthContext(ator='rsm-08-test', via_token=False)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[require_service_case_auth] = _auth_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_service_case_auth, None)


@pytest.fixture
def service_id() -> str:
    value = str(uuid4())
    db = TestingSession()
    try:
        db.add(
            ServicoTI(
                servico_id=value,
                codigo=f'RSM08_{value[:8].upper()}',
                nome='Servico RSM-08 teste',
                criticidade='alta',
                responsavel_tecnico='rsm-08-test',
                responsavel_negocio='rsm-08-test',
                ativo=True,
            )
        )
        db.commit()
    finally:
        db.close()
    return value


def _key(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _create(case_type: str, service_id: str) -> dict:
    response = client.post(
        '/v1/service-cases',
        json={
            'case_type': case_type,
            'service_id': service_id,
            'requester': 'rsm-08-test',
            'impact': 'HIGH',
            'urgency': 'HIGH',
            'idempotency_key': _key(f'{case_type}-{uuid4()}'),
            'event_id': str(uuid4()),
            'source': 'reqsys',
        },
        headers={'X-Correlation-ID': f'rsm08-create-{uuid4().hex}'},
    )
    assert response.status_code == 200
    return response.json()['data']['case']


def test_incident_problem_link_root_cause_readback_and_replay(service_id):
    incident = _create('INCIDENT', service_id)
    problem = _create('PROBLEM', service_id)
    link_event = str(uuid4())

    first = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': problem['case_id'], 'event_id': link_event},
        headers={'X-Correlation-ID': 'rsm08-link'},
    )
    assert first.status_code == 200
    assert first.json()['data']['duplicate'] is False

    same_event = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': problem['case_id'], 'event_id': link_event},
        headers={'X-Correlation-ID': 'rsm08-link-replay'},
    )
    assert same_event.status_code == 200
    assert same_event.json()['data']['duplicate'] is True

    logical_replay = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': problem['case_id'], 'event_id': str(uuid4())},
        headers={'X-Correlation-ID': 'rsm08-link-logical-replay'},
    )
    assert logical_replay.status_code == 200
    assert logical_replay.json()['data']['duplicate'] is True

    rca_event = str(uuid4())
    rca_payload = {
        'event_id': rca_event,
        'statement': 'Pool de conexão esgotado por configuração inválida.',
        'evidence_uri': 'urn:reqsys:rsm08:root-cause',
        'evidence_sha256': _key('root-cause'),
    }
    rca = client.post(
        f"/v1/service-cases/{problem['case_id']}/root-causes",
        json=rca_payload,
        headers={'X-Correlation-ID': 'rsm08-rca'},
    )
    assert rca.status_code == 200
    assert rca.json()['data']['duplicate'] is False

    rca_replay = client.post(
        f"/v1/service-cases/{problem['case_id']}/root-causes",
        json=rca_payload,
        headers={'X-Correlation-ID': 'rsm08-rca-replay'},
    )
    assert rca_replay.status_code == 200
    assert rca_replay.json()['data']['duplicate'] is True

    incident_read = client.get(f"/v1/service-cases/{incident['case_id']}")
    assert incident_read.status_code == 200
    related = incident_read.json()['data']['related_cases']
    assert related == [
        {
            'relation': 'INCIDENT_TO_PROBLEM',
            'case_id': problem['case_id'],
            'case_type': 'PROBLEM',
            'event_id': link_event,
            'correlation_id': 'rsm08-link',
        }
    ]

    problem_read = client.get(f"/v1/service-cases/{problem['case_id']}")
    assert problem_read.status_code == 200
    causes = problem_read.json()['data']['root_causes']
    assert len(causes) == 1
    assert causes[0]['statement'] == rca_payload['statement']
    assert causes[0]['evidence_sha256'] == rca_payload['evidence_sha256']

    db = TestingSession()
    try:
        assert (
            db.query(IncidentProblemLinkRecord)
            .filter_by(incident_case_id=incident['case_id'], problem_case_id=problem['case_id'])
            .count()
            == 1
        )
        assert db.query(ProblemRootCauseRecord).filter_by(problem_case_id=problem['case_id']).count() == 1
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(case_id=incident['case_id'], event_type='INCIDENT_LINKED_TO_PROBLEM')
            .count()
            == 1
        )
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(case_id=problem['case_id'], event_type='PROBLEM_ROOT_CAUSE_RECORDED')
            .count()
            == 1
        )
    finally:
        db.close()


def test_invalid_relations_fail_closed_without_mutation(service_id):
    incident = _create('INCIDENT', service_id)
    problem = _create('PROBLEM', service_id)
    request = _create('REQUEST', service_id)

    invalid_source = client.post(
        f"/v1/service-cases/{request['case_id']}/problem-links",
        json={'problem_case_id': problem['case_id'], 'event_id': str(uuid4())},
    )
    assert invalid_source.status_code == 422

    invalid_target = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': incident['case_id'], 'event_id': str(uuid4())},
    )
    assert invalid_target.status_code == 422

    invalid_rca = client.post(
        f"/v1/service-cases/{incident['case_id']}/root-causes",
        json={
            'event_id': str(uuid4()),
            'statement': 'Não deve persistir',
            'evidence_uri': 'urn:reqsys:rsm08:negative',
            'evidence_sha256': _key('negative'),
        },
    )
    assert invalid_rca.status_code == 422

    db = TestingSession()
    try:
        assert db.query(IncidentProblemLinkRecord).count() == 0
        assert db.query(ProblemRootCauseRecord).count() == 0
        assert (
            db.query(ServiceCaseEventRecord)
            .filter(
                ServiceCaseEventRecord.event_type.in_(
                    ['INCIDENT_LINKED_TO_PROBLEM', 'PROBLEM_ROOT_CAUSE_RECORDED']
                )
            )
            .count()
            == 0
        )
    finally:
        db.close()


def test_conflicting_event_reuse_is_rejected(service_id):
    incident = _create('INCIDENT', service_id)
    problem_a = _create('PROBLEM', service_id)
    problem_b = _create('PROBLEM', service_id)
    event_id = str(uuid4())

    first = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': problem_a['case_id'], 'event_id': event_id},
    )
    assert first.status_code == 200

    conflict = client.post(
        f"/v1/service-cases/{incident['case_id']}/problem-links",
        json={'problem_case_id': problem_b['case_id'], 'event_id': event_id},
    )
    assert conflict.status_code == 409

    db = TestingSession()
    try:
        assert db.query(IncidentProblemLinkRecord).count() == 1
    finally:
        db.close()
