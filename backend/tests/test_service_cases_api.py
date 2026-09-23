from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.service_cases import (
    ServiceCaseEventRecord,
    ServiceCaseRecord,
    _safe_log_value,
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
    return ServiceAuthContext(ator='rsm-test', via_token=False)


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
                codigo=f'RSM_{value[:8].upper()}',
                nome='Servico RSM teste',
                criticidade='media',
                responsavel_tecnico='rsm-test',
                responsavel_negocio='rsm-test',
                ativo=True,
            )
        )
        db.commit()
    finally:
        db.close()
    return value


def _key(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _create_payload(service_id: str, logical: str) -> dict:
    return {
        'case_type': 'REQUEST',
        'service_id': service_id,
        'requester': 'rsm-test',
        'impact': 'MEDIUM',
        'urgency': 'HIGH',
        'idempotency_key': _key(logical),
        'event_id': str(uuid4()),
        'source': 'reqsys',
    }


def _transition(case_id: str, target: str, version: int, *, evidence: bool = False):
    body = {
        'target_state': target,
        'expected_version': version,
        'event_id': str(uuid4()),
    }
    if evidence:
        body['evidence_uri'] = f'urn:reqsys:test:{case_id}'
        body['evidence_sha256'] = _key(case_id)
    return client.post(
        f'/v1/service-cases/{case_id}/transitions',
        json=body,
        headers={'X-Correlation-ID': f'test-{case_id}'},
    )


def test_create_and_replay_converge_without_duplicate(service_id):
    payload = _create_payload(service_id, f'replay-{uuid4()}')
    first = client.post(
        '/v1/service-cases',
        json=payload,
        headers={'X-Correlation-ID': 'rsm-create-first'},
    )
    assert first.status_code == 200
    case_id = first.json()['data']['case']['case_id']
    assert first.json()['data']['duplicate'] is False

    replay = dict(payload)
    replay['event_id'] = str(uuid4())
    second = client.post(
        '/v1/service-cases',
        json=replay,
        headers={'X-Correlation-ID': 'rsm-create-replay'},
    )
    assert second.status_code == 200
    assert second.json()['data']['duplicate'] is True
    assert second.json()['data']['case']['case_id'] == case_id

    db = TestingSession()
    try:
        assert db.query(ServiceCaseRecord).filter_by(idempotency_key=payload['idempotency_key']).count() == 1
        assert db.query(ServiceCaseEventRecord).filter_by(case_id=case_id).count() == 1
    finally:
        db.close()


def test_terminal_flow_negative_control_and_independent_state(service_id):
    payload = _create_payload(service_id, f'terminal-{uuid4()}')
    created = client.post(
        '/v1/service-cases',
        json=payload,
        headers={'X-Correlation-ID': 'rsm-terminal'},
    )
    assert created.status_code == 200
    case = created.json()['data']['case']

    for target in ('TRIAGE', 'IN_PROGRESS'):
        response = _transition(case['case_id'], target, case['version'])
        assert response.status_code == 200
        case = response.json()['data']['case']

    resolved = _transition(case['case_id'], 'RESOLVED', case['version'], evidence=True)
    assert resolved.status_code == 200
    case = resolved.json()['data']['case']

    closed = _transition(case['case_id'], 'CLOSED', case['version'])
    assert closed.status_code == 200
    case = closed.json()['data']['case']
    assert case['state'] == 'CLOSED'

    db = TestingSession()
    try:
        before_events = db.query(ServiceCaseEventRecord).filter_by(case_id=case['case_id']).count()
        persisted = db.get(ServiceCaseRecord, case['case_id'])
        assert persisted is not None
        assert persisted.state == 'CLOSED'
        assert persisted.version == 5
    finally:
        db.close()

    invalid = _transition(case['case_id'], 'IN_PROGRESS', case['version'])
    assert invalid.status_code == 409

    db = TestingSession()
    try:
        persisted = db.get(ServiceCaseRecord, case['case_id'])
        assert persisted is not None
        assert persisted.state == 'CLOSED'
        assert db.query(ServiceCaseEventRecord).filter_by(case_id=case['case_id']).count() == before_events
    finally:
        db.close()


def test_resolution_requires_evidence(service_id):
    payload = _create_payload(service_id, f'evidence-{uuid4()}')
    created = client.post('/v1/service-cases', json=payload)
    case = created.json()['data']['case']
    for target in ('TRIAGE', 'IN_PROGRESS'):
        response = _transition(case['case_id'], target, case['version'])
        case = response.json()['data']['case']

    response = _transition(case['case_id'], 'RESOLVED', case['version'])
    assert response.status_code == 409

    db = TestingSession()
    try:
        persisted = db.get(ServiceCaseRecord, case['case_id'])
        assert persisted is not None
        assert persisted.state == 'IN_PROGRESS'
    finally:
        db.close()


def test_stale_version_is_rejected(service_id):
    payload = _create_payload(service_id, f'concurrency-{uuid4()}')
    created = client.post('/v1/service-cases', json=payload)
    case = created.json()['data']['case']

    first = _transition(case['case_id'], 'TRIAGE', case['version'])
    assert first.status_code == 200

    stale = _transition(case['case_id'], 'CANCELED', case['version'])
    assert stale.status_code == 409


def test_invalid_idempotency_key_fails_before_persistence(service_id):
    payload = _create_payload(service_id, f'invalid-key-{uuid4()}')
    payload['idempotency_key'] = 'not-a-sha256'
    response = client.post('/v1/service-cases', json=payload)
    assert response.status_code == 422


def test_log_value_removes_line_breaks():
    assert _safe_log_value('corr\r\nforged') == 'corrforged'


def test_create_rejects_missing_service():
    payload = _create_payload(str(uuid4()), f'missing-service-{uuid4()}')
    response = client.post('/v1/service-cases', json=payload)
    assert response.status_code == 404


def test_create_rejects_inactive_service():
    value = str(uuid4())
    db = TestingSession()
    try:
        db.add(
            ServicoTI(
                servico_id=value,
                codigo=f'RSM_{value[:8].upper()}',
                nome='Servico RSM inativo',
                criticidade='media',
                responsavel_tecnico='rsm-test',
                responsavel_negocio='rsm-test',
                ativo=False,
            )
        )
        db.commit()
    finally:
        db.close()

    payload = _create_payload(value, f'inactive-service-{uuid4()}')
    response = client.post('/v1/service-cases', json=payload)
    assert response.status_code == 409


def test_get_case_returns_persisted_case_and_events(service_id):
    payload = _create_payload(service_id, f'get-case-{uuid4()}')
    created = client.post('/v1/service-cases', json=payload)
    assert created.status_code == 200
    case_id = created.json()['data']['case']['case_id']

    response = client.get(f'/v1/service-cases/{case_id}')
    assert response.status_code == 200
    body = response.json()['data']
    assert body['case_id'] == case_id
    assert body['state'] == 'NEW'
    assert body['allowed_transitions'] == ['CANCELED', 'TRIAGE']
    assert len(body['events']) == 1
    assert body['events'][0]['event_type'] == 'CASE_CREATED'
    assert body['events'][0]['to_state'] == 'NEW'


def test_get_case_missing_returns_404():
    response = client.get(f'/v1/service-cases/{uuid4()}')
    assert response.status_code == 404


def test_transition_replay_is_idempotent_and_conflicting_reuse_fails(service_id):
    payload = _create_payload(service_id, f'transition-replay-{uuid4()}')
    created = client.post('/v1/service-cases', json=payload)
    assert created.status_code == 200
    case = created.json()['data']['case']
    event_id = str(uuid4())
    body = {
        'target_state': 'TRIAGE',
        'expected_version': case['version'],
        'event_id': event_id,
    }

    first = client.post(f"/v1/service-cases/{case['case_id']}/transitions", json=body)
    assert first.status_code == 200
    assert first.json()['data']['duplicate'] is False

    replay = client.post(f"/v1/service-cases/{case['case_id']}/transitions", json=body)
    assert replay.status_code == 200
    assert replay.json()['data']['duplicate'] is True
    assert replay.json()['data']['case']['version'] == 2

    conflicting = dict(body)
    conflicting['target_state'] = 'CANCELED'
    conflicting['expected_version'] = 2
    conflict = client.post(f"/v1/service-cases/{case['case_id']}/transitions", json=conflicting)
    assert conflict.status_code == 409

    db = TestingSession()
    try:
        assert db.query(ServiceCaseEventRecord).filter_by(case_id=case['case_id']).count() == 2
    finally:
        db.close()


def test_transition_missing_case_returns_404():
    body = {
        'target_state': 'TRIAGE',
        'expected_version': 1,
        'event_id': str(uuid4()),
    }
    response = client.post(f'/v1/service-cases/{uuid4()}/transitions', json=body)
    assert response.status_code == 404



def test_transition_response_refreshes_allowed_transitions(service_id):
    payload = _create_payload(service_id, f'allowed-transitions-{uuid4()}')
    created = client.post('/v1/service-cases', json=payload)
    assert created.status_code == 200
    case = created.json()['data']['case']
    assert case['allowed_transitions'] == ['CANCELED', 'TRIAGE']

    transitioned = _transition(case['case_id'], 'TRIAGE', case['version'])
    assert transitioned.status_code == 200
    updated = transitioned.json()['data']['case']
    assert updated['state'] == 'TRIAGE'
    assert updated['allowed_transitions'] == ['CANCELED', 'IN_PROGRESS', 'PENDING_APPROVAL']
