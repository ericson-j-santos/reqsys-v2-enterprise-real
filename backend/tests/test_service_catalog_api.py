from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.service_cases import ServiceCaseRecord, require_service_case_auth
from app.api.service_catalog import ServiceCaseOfferingRecord, ServiceOfferingRecord
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

FIELD_SCHEMA = {
    'schema_version': '1.0.0',
    'fields': [
        {'key': 'justificativa', 'label': 'Justificativa', 'type': 'STRING', 'required': True, 'max_length': 120},
        {'key': 'ambiente', 'label': 'Ambiente', 'type': 'ENUM', 'required': True, 'options': ['DEV', 'HML']},
        {'key': 'quantidade', 'label': 'Quantidade', 'type': 'INTEGER', 'min_value': 1, 'max_value': 10},
    ],
}


def _db_override():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def _auth_override():
    return ServiceAuthContext(ator='rsm-catalog-test', via_token=False)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[require_service_case_auth] = _auth_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_service_case_auth, None)


def _key(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _service(active: bool = True) -> str:
    value = str(uuid4())
    db = TestingSession()
    try:
        db.add(
            ServicoTI(
                servico_id=value,
                codigo=f'CAT_{value[:8].upper()}',
                nome='Servico catalogo teste',
                criticidade='media',
                responsavel_tecnico='rsm-test',
                responsavel_negocio='rsm-test',
                ativo=active,
            )
        )
        db.commit()
    finally:
        db.close()
    return value


@pytest.fixture
def service_id() -> str:
    return _service()


def _offering_payload(service_id: str, **overrides) -> dict:
    payload = {
        'service_id': service_id,
        'code': f'OFF-{uuid4().hex[:10].upper()}',
        'name': 'Acesso a relatorio gerencial',
        'description': 'Oferta minima de catalogo para testes',
        'active': True,
        'field_schema': FIELD_SCHEMA,
    }
    payload.update(overrides)
    return payload


def _create_offering(service_id: str, **overrides):
    return client.post(
        '/v1/service-offerings',
        json=_offering_payload(service_id, **overrides),
        headers={'X-Correlation-ID': f'cat-{uuid4().hex[:8]}'},
    )


def _request_payload(logical: str, **overrides) -> dict:
    payload = {
        'requester': 'rsm-catalog-test',
        'impact': 'MEDIUM',
        'urgency': 'HIGH',
        'idempotency_key': _key(logical),
        'event_id': str(uuid4()),
        'source': 'reqsys',
        'fields': {'justificativa': 'acesso mensal', 'ambiente': 'DEV', 'quantidade': 2},
    }
    payload.update(overrides)
    return payload


def _open_request(offering_id: str, payload: dict, correlation_id: str):
    return client.post(
        f'/v1/service-offerings/{offering_id}/requests',
        json=payload,
        headers={'X-Correlation-ID': correlation_id},
    )


def test_registro_de_oferta_e_idempotente_por_code(service_id):
    payload = _offering_payload(service_id)
    first = client.post('/v1/service-offerings', json=payload)
    assert first.status_code == 200
    assert first.json()['data']['duplicate'] is False
    offering_id = first.json()['data']['offering']['offering_id']

    second = client.post('/v1/service-offerings', json=payload)
    assert second.status_code == 200
    assert second.json()['data']['duplicate'] is True
    assert second.json()['data']['offering']['offering_id'] == offering_id

    db = TestingSession()
    try:
        assert db.query(ServiceOfferingRecord).filter_by(code=payload['code']).count() == 1
    finally:
        db.close()


def test_oferta_exige_servico_existente_e_ativo():
    inexistente = _create_offering(str(uuid4()))
    assert inexistente.status_code == 404

    inativo = _create_offering(_service(active=False))
    assert inativo.status_code == 409


def test_field_schema_invalido_e_rejeitado(service_id):
    resposta = _create_offering(
        service_id,
        field_schema={'fields': [{'key': 'a', 'label': 'A', 'type': 'ENUM'}]},
    )
    assert resposta.status_code == 422


def test_abertura_valida_cria_request_vinculado_ao_catalogo(service_id):
    offering = _create_offering(service_id).json()['data']['offering']
    payload = _request_payload(f'ok-{uuid4()}')
    correlation_id = 'cat-request-ok'

    resposta = _open_request(offering['offering_id'], payload, correlation_id)
    assert resposta.status_code == 200
    data = resposta.json()['data']
    assert data['duplicate'] is False
    assert data['case']['case_type'] == 'REQUEST'
    assert data['case']['service_id'] == service_id
    assert data['case']['correlation_id'] == correlation_id
    assert data['offering_id'] == offering['offering_id']
    assert data['submitted_fields'] == payload['fields']

    db = TestingSession()
    try:
        link = db.get(ServiceCaseOfferingRecord, data['case']['case_id'])
        assert link is not None
        assert link.offering_id == offering['offering_id']
        assert link.correlation_id == correlation_id
        case = db.get(ServiceCaseRecord, data['case']['case_id'])
        assert case is not None and case.case_type == 'REQUEST'
    finally:
        db.close()


def test_replay_nao_cria_segundo_caso(service_id):
    offering = _create_offering(service_id).json()['data']['offering']
    payload = _request_payload(f'replay-{uuid4()}')

    first = _open_request(offering['offering_id'], payload, 'cat-replay-1')
    assert first.status_code == 200
    case_id = first.json()['data']['case']['case_id']

    replay = dict(payload)
    replay['event_id'] = str(uuid4())
    second = _open_request(offering['offering_id'], replay, 'cat-replay-2')
    assert second.status_code == 200
    assert second.json()['data']['duplicate'] is True
    assert second.json()['data']['case']['case_id'] == case_id

    db = TestingSession()
    try:
        assert (
            db.query(ServiceCaseRecord)
            .filter_by(idempotency_key=payload['idempotency_key'])
            .count()
            == 1
        )
        assert db.query(ServiceCaseOfferingRecord).filter_by(case_id=case_id).count() == 1
    finally:
        db.close()


def test_oferta_inexistente_e_rejeitada(service_id):
    resposta = _open_request(str(uuid4()), _request_payload(f'nf-{uuid4()}'), 'cat-nf')
    assert resposta.status_code == 404


def test_oferta_inativa_e_rejeitada(service_id):
    offering = _create_offering(service_id, active=False).json()['data']['offering']
    payload = _request_payload(f'inativa-{uuid4()}')

    resposta = _open_request(offering['offering_id'], payload, 'cat-inativa')
    assert resposta.status_code == 409

    db = TestingSession()
    try:
        assert (
            db.query(ServiceCaseRecord)
            .filter_by(idempotency_key=payload['idempotency_key'])
            .count()
            == 0
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    'fields',
    [
        {'ambiente': 'DEV'},
        {'justificativa': 'ok', 'ambiente': 'PROD'},
        {'justificativa': 'ok', 'ambiente': 'DEV', 'nao_declarado': 'x'},
        {'justificativa': 'ok', 'ambiente': 'DEV', 'quantidade': '2'},
        {'justificativa': 'x' * 200, 'ambiente': 'DEV'},
    ],
)
def test_entrada_invalida_nao_cria_caso(service_id, fields):
    offering = _create_offering(service_id).json()['data']['offering']
    payload = _request_payload(f'invalida-{uuid4()}', fields=fields)

    resposta = _open_request(offering['offering_id'], payload, 'cat-invalida')
    assert resposta.status_code == 422

    db = TestingSession()
    try:
        assert (
            db.query(ServiceCaseRecord)
            .filter_by(idempotency_key=payload['idempotency_key'])
            .count()
            == 0
        )
    finally:
        db.close()


def test_idempotency_key_de_outra_oferta_e_rejeitada(service_id):
    primeira = _create_offering(service_id).json()['data']['offering']
    segunda = _create_offering(service_id).json()['data']['offering']
    payload = _request_payload(f'colisao-{uuid4()}')

    assert _open_request(primeira['offering_id'], payload, 'cat-colisao-1').status_code == 200

    colisao = dict(payload)
    colisao['event_id'] = str(uuid4())
    resposta = _open_request(segunda['offering_id'], colisao, 'cat-colisao-2')
    assert resposta.status_code == 409

    db = TestingSession()
    try:
        assert (
            db.query(ServiceCaseOfferingRecord)
            .filter_by(offering_id=segunda['offering_id'])
            .count()
            == 0
        )
    finally:
        db.close()


def test_leitura_independente_lista_e_detalha_oferta(service_id):
    offering = _create_offering(service_id).json()['data']['offering']

    detalhe = client.get(f"/v1/service-offerings/{offering['offering_id']}")
    assert detalhe.status_code == 200
    assert detalhe.json()['data']['offering']['code'] == offering['code']

    listagem = client.get('/v1/service-offerings', params={'service_id': service_id, 'active': True})
    assert listagem.status_code == 200
    codigos = [item['code'] for item in listagem.json()['data']['offerings']]
    assert offering['code'] in codigos

    assert client.get(f'/v1/service-offerings/{uuid4()}').status_code == 404
