from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.service_case_operations import (
    CaseApprovalRecord,
    CaseAssignmentRecord,
    CaseSlaRecord,
)
from app.api.service_cases import ServiceCaseEventRecord, require_service_case_auth
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
    return ServiceAuthContext(ator='rsm-ops-test', via_token=False)


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[require_service_case_auth] = _auth_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_service_case_auth, None)


def _key(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


@pytest.fixture
def service_id() -> str:
    value = str(uuid4())
    db = TestingSession()
    try:
        db.add(
            ServicoTI(
                servico_id=value,
                codigo=f'OPS_{value[:8].upper()}',
                nome='Servico operacoes teste',
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


@pytest.fixture
def case(service_id: str) -> dict:
    response = client.post(
        '/v1/service-cases',
        json={
            'case_type': 'REQUEST',
            'service_id': service_id,
            'requester': 'rsm-ops-test',
            'impact': 'HIGH',
            'urgency': 'HIGH',
            'idempotency_key': _key(f'ops-{uuid4()}'),
            'event_id': str(uuid4()),
            'source': 'reqsys',
        },
        headers={'X-Correlation-ID': 'ops-create'},
    )
    assert response.status_code == 200
    return response.json()['data']['case']


@pytest.fixture
def policy() -> dict:
    response = client.post(
        '/v1/sla-policies',
        json={
            'code': f'SLA-{uuid4().hex[:8].upper()}',
            'name': 'Politica padrao',
            'response_minutes': 30,
            'resolution_minutes': 240,
        },
    )
    assert response.status_code == 200
    return response.json()['data']['policy']


def _transition(case_id: str, target: str, version: int, *, evidence: bool = False):
    body = {'target_state': target, 'expected_version': version, 'event_id': str(uuid4())}
    if evidence:
        body['evidence_uri'] = f'urn:reqsys:ops:{case_id}'
        body['evidence_sha256'] = _key(case_id)
    return client.post(f'/v1/service-cases/{case_id}/transitions', json=body)


# --- SLA ------------------------------------------------------------------


def test_politica_de_sla_e_idempotente_por_code():
    payload = {
        'code': f'SLA-{uuid4().hex[:8].upper()}',
        'name': 'Politica idempotente',
        'response_minutes': 15,
        'resolution_minutes': 60,
    }
    primeira = client.post('/v1/sla-policies', json=payload)
    segunda = client.post('/v1/sla-policies', json=payload)
    assert primeira.status_code == 200 and primeira.json()['data']['duplicate'] is False
    assert segunda.status_code == 200 and segunda.json()['data']['duplicate'] is True
    assert segunda.json()['data']['policy']['policy_id'] == primeira.json()['data']['policy']['policy_id']


def test_politica_com_resolucao_menor_que_resposta_e_rejeitada():
    resposta = client.post(
        '/v1/sla-policies',
        json={
            'code': f'SLA-{uuid4().hex[:8].upper()}',
            'name': 'Incoerente',
            'response_minutes': 120,
            'resolution_minutes': 60,
        },
    )
    assert resposta.status_code == 422


def test_sla_aplicado_e_deterministico_e_idempotente(case, policy):
    body = {'policy_id': policy['policy_id'], 'event_id': str(uuid4())}
    primeira = client.post(f"/v1/service-cases/{case['case_id']}/sla", json=body)
    assert primeira.status_code == 200
    assert primeira.json()['data']['duplicate'] is False
    prazos = primeira.json()['data']['sla']
    # impact=HIGH + urgency=HIGH => peso 3+3=6 => P2 => fator 2
    assert prazos['priority'] == 'P2'

    replay = client.post(f"/v1/service-cases/{case['case_id']}/sla", json=body)
    assert replay.status_code == 200
    assert replay.json()['data']['duplicate'] is True
    assert replay.json()['data']['sla'] == prazos

    db = TestingSession()
    try:
        assert db.query(CaseSlaRecord).filter_by(case_id=case['case_id']).count() == 1
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(case_id=case['case_id'], event_type='SLA_APPLIED')
            .count()
            == 1
        )
    finally:
        db.close()


def test_sla_com_politica_inexistente_e_rejeitado(case):
    resposta = client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': str(uuid4()), 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 404


def test_segunda_politica_divergente_e_rejeitada(case, policy):
    outra = client.post(
        '/v1/sla-policies',
        json={
            'code': f'SLA-{uuid4().hex[:8].upper()}',
            'name': 'Outra',
            'response_minutes': 10,
            'resolution_minutes': 20,
        },
    ).json()['data']['policy']
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    resposta = client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': outra['policy_id'], 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 409


def test_leitura_de_sla_rejeita_instante_anterior_ao_inicio(case, policy):
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    resposta = client.get(
        f"/v1/service-cases/{case['case_id']}/operations",
        params={'evaluated_at': '2000-01-01T00:00:00+00:00'},
    )
    assert resposta.status_code == 422


def test_leitura_de_sla_detecta_estouro_em_instante_futuro(case, policy):
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    resposta = client.get(
        f"/v1/service-cases/{case['case_id']}/operations",
        params={'evaluated_at': '2030-01-01T00:00:00+00:00'},
    )
    assert resposta.status_code == 200
    assert resposta.json()['data']['sla']['state'] == 'RESOLUTION_BREACHED'


# --- atribuição -----------------------------------------------------------


def test_atribuicao_e_auditada_e_idempotente(case):
    body = {'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': str(uuid4())}
    primeira = client.post(f"/v1/service-cases/{case['case_id']}/assignments", json=body)
    assert primeira.status_code == 200
    assert primeira.json()['data']['duplicate'] is False
    assert primeira.json()['data']['assignment']['previous_group'] is None

    replay = client.post(f"/v1/service-cases/{case['case_id']}/assignments", json=body)
    assert replay.status_code == 200
    assert replay.json()['data']['duplicate'] is True

    segunda = client.post(
        f"/v1/service-cases/{case['case_id']}/assignments",
        json={'assignment_group': 'Engenharia', 'assignee': 'bruno', 'event_id': str(uuid4())},
    )
    assert segunda.status_code == 200
    dados = segunda.json()['data']['assignment']
    assert dados['previous_group'] == 'Sustentacao'
    assert dados['previous_assignee'] == 'ana'
    assert dados['sequence'] == 2

    db = TestingSession()
    try:
        historico = (
            db.query(CaseAssignmentRecord)
            .filter_by(case_id=case['case_id'])
            .order_by(CaseAssignmentRecord.sequence)
            .all()
        )
        assert [item.sequence for item in historico] == [1, 2]
        assert historico[0].assignment_group == 'Sustentacao'
    finally:
        db.close()


def test_reatribuicao_identica_nao_gera_novo_registro(case):
    body = {'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': str(uuid4())}
    client.post(f"/v1/service-cases/{case['case_id']}/assignments", json=body)
    repetida = client.post(
        f"/v1/service-cases/{case['case_id']}/assignments",
        json={'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': str(uuid4())},
    )
    assert repetida.status_code == 200
    assert repetida.json()['data']['duplicate'] is True

    db = TestingSession()
    try:
        assert db.query(CaseAssignmentRecord).filter_by(case_id=case['case_id']).count() == 1
    finally:
        db.close()


def test_atribuicao_sem_grupo_e_rejeitada(case):
    resposta = client.post(
        f"/v1/service-cases/{case['case_id']}/assignments",
        json={'assignment_group': '   ', 'assignee': 'ana', 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 422


def test_atribuicao_em_caso_inexistente_e_rejeitada():
    resposta = client.post(
        f'/v1/service-cases/{uuid4()}/assignments',
        json={'assignment_group': 'Sustentacao', 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 404


def test_event_id_reaproveitado_para_outro_efeito_e_rejeitado(case, policy):
    event_id = str(uuid4())
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': event_id},
    )
    resposta = client.post(
        f"/v1/service-cases/{case['case_id']}/assignments",
        json={'assignment_group': 'Sustentacao', 'event_id': event_id},
    )
    assert resposta.status_code == 409


# --- aprovação ------------------------------------------------------------


def _to_pending_approval(case: dict) -> int:
    resposta = _transition(case['case_id'], 'TRIAGE', case['version'])
    assert resposta.status_code == 200
    versao = resposta.json()['data']['case']['version']
    resposta = _transition(case['case_id'], 'PENDING_APPROVAL', versao)
    assert resposta.status_code == 200
    return resposta.json()['data']['case']['version']


def test_transicao_sob_portao_e_bloqueada_sem_aprovacao(case):
    versao = _to_pending_approval(case)
    bloqueada = _transition(case['case_id'], 'IN_PROGRESS', versao)
    assert bloqueada.status_code == 409
    assert 'APPROVED' in bloqueada.json()['detail']

    leitura = client.get(f"/v1/service-cases/{case['case_id']}/operations")
    assert leitura.json()['data']['state'] == 'PENDING_APPROVAL'


def test_aprovacao_pendente_nao_libera_transicao(case):
    versao = _to_pending_approval(case)
    client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor', 'event_id': str(uuid4())},
    )
    assert _transition(case['case_id'], 'IN_PROGRESS', versao).status_code == 409


def test_rejeicao_preserva_historico_e_mantem_bloqueio(case):
    versao = _to_pending_approval(case)
    aprovacao = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor', 'event_id': str(uuid4())},
    ).json()['data']['approval']

    rejeicao = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals/{aprovacao['approval_id']}/decision",
        json={'decision': 'REJECTED', 'event_id': str(uuid4()), 'reason': 'fora da janela'},
    )
    assert rejeicao.status_code == 200
    assert rejeicao.json()['data']['approval']['status'] == 'REJECTED'
    assert rejeicao.json()['data']['approval']['decision_reason'] == 'fora da janela'

    assert _transition(case['case_id'], 'IN_PROGRESS', versao).status_code == 409

    db = TestingSession()
    try:
        registro = db.get(CaseApprovalRecord, aprovacao['approval_id'])
        assert registro.status == 'REJECTED'
        assert registro.decision_reason == 'fora da janela'
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(case_id=case['case_id'], event_type='APPROVAL_DECIDED')
            .count()
            == 1
        )
    finally:
        db.close()


def test_decisao_e_terminal_e_idempotente(case):
    _to_pending_approval(case)
    aprovacao = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor', 'event_id': str(uuid4())},
    ).json()['data']['approval']
    decision_event = str(uuid4())
    url = f"/v1/service-cases/{case['case_id']}/approvals/{aprovacao['approval_id']}/decision"

    primeira = client.post(url, json={'decision': 'APPROVED', 'event_id': decision_event})
    assert primeira.status_code == 200 and primeira.json()['data']['duplicate'] is False

    replay = client.post(url, json={'decision': 'APPROVED', 'event_id': decision_event})
    assert replay.status_code == 200 and replay.json()['data']['duplicate'] is True

    reversao = client.post(url, json={'decision': 'REJECTED', 'event_id': str(uuid4())})
    assert reversao.status_code == 422

    db = TestingSession()
    try:
        assert (
            db.query(ServiceCaseEventRecord)
            .filter_by(case_id=case['case_id'], event_type='APPROVAL_DECIDED')
            .count()
            == 1
        )
    finally:
        db.close()


def test_aprovacao_valida_libera_a_transicao_apos_rejeicao(case):
    versao = _to_pending_approval(case)
    rejeitada = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor-1', 'event_id': str(uuid4())},
    ).json()['data']['approval']
    client.post(
        f"/v1/service-cases/{case['case_id']}/approvals/{rejeitada['approval_id']}/decision",
        json={'decision': 'REJECTED', 'event_id': str(uuid4())},
    )
    aprovada = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor-2', 'event_id': str(uuid4())},
    ).json()['data']['approval']
    client.post(
        f"/v1/service-cases/{case['case_id']}/approvals/{aprovada['approval_id']}/decision",
        json={'decision': 'APPROVED', 'event_id': str(uuid4())},
    )

    liberada = _transition(case['case_id'], 'IN_PROGRESS', versao)
    assert liberada.status_code == 200
    assert liberada.json()['data']['case']['state'] == 'IN_PROGRESS'

    leitura = client.get(f"/v1/service-cases/{case['case_id']}/operations").json()['data']
    assert [item['status'] for item in leitura['approvals']] == ['REJECTED', 'APPROVED']
    assert leitura['sla'] is None


def test_decisao_em_aprovacao_de_outro_caso_e_rejeitada(case, service_id):
    _to_pending_approval(case)
    aprovacao = client.post(
        f"/v1/service-cases/{case['case_id']}/approvals",
        json={'approver': 'gestor', 'event_id': str(uuid4())},
    ).json()['data']['approval']
    resposta = client.post(
        f"/v1/service-cases/{uuid4()}/approvals/{aprovacao['approval_id']}/decision",
        json={'decision': 'APPROVED', 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 404


# --- leitura consolidada --------------------------------------------------


def test_leitura_consolidada_reflete_estado_e_historico(case, policy):
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    client.post(
        f"/v1/service-cases/{case['case_id']}/assignments",
        json={'assignment_group': 'Sustentacao', 'assignee': 'ana', 'event_id': str(uuid4())},
    )
    leitura = client.get(f"/v1/service-cases/{case['case_id']}/operations")
    assert leitura.status_code == 200
    dados = leitura.json()['data']
    assert dados['current_assignment']['assignment_group'] == 'Sustentacao'
    assert dados['sla']['state'] == 'ON_TIME'
    assert dados['sla']['first_response_at'] is None
    tipos = {item['event_type'] for item in dados['history']}
    assert {'CASE_CREATED', 'SLA_APPLIED', 'ASSIGNMENT_CHANGED'} <= tipos


def test_leitura_de_caso_inexistente_e_404():
    assert client.get(f'/v1/service-cases/{uuid4()}/operations').status_code == 404


def test_primeira_resposta_deriva_do_historico(case, policy):
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    versao = _transition(case['case_id'], 'TRIAGE', case['version']).json()['data']['case']['version']
    _transition(case['case_id'], 'IN_PROGRESS', versao)

    dados = client.get(f"/v1/service-cases/{case['case_id']}/operations").json()['data']
    assert dados['sla']['first_response_at'] is not None
    assert dados['sla']['resolved_at'] is None


def test_politica_inexistente_e_404_mesmo_com_sla_ja_aplicado(case, policy):
    """Regressão: a ordem de validação não pode mascarar 404 com 409.

    Detectado pelo E2E físico, não pelo teste anterior, que usava caso sem SLA.
    """
    client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': policy['policy_id'], 'event_id': str(uuid4())},
    )
    resposta = client.post(
        f"/v1/service-cases/{case['case_id']}/sla",
        json={'policy_id': str(uuid4()), 'event_id': str(uuid4())},
    )
    assert resposta.status_code == 404
