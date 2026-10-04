from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.service_management import (
    ApprovalStatus,
    ServiceCasePriority,
    ServiceCaseState,
    ServiceManagementValidationError,
    SlaPolicy,
)
from app.domain.service_operations import (
    PRIORITY_SLA_FACTOR,
    ApprovalRequiredError,
    AssignmentValidationError,
    SlaState,
    SlaTargets,
    SlaViolationError,
    assert_approval_allows_transition,
    calculate_sla_targets,
    evaluate_sla,
    plan_assignment,
    requires_approval,
    validate_approval_decision,
)

START = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def policy() -> SlaPolicy:
    return SlaPolicy(
        policy_id=str(uuid4()),
        name='Padrao',
        response_minutes=30,
        resolution_minutes=240,
    )


# --- SLA determinístico ---------------------------------------------------


def test_sla_e_deterministico_para_a_mesma_entrada(policy: SlaPolicy):
    primeiro = calculate_sla_targets(policy, ServiceCasePriority.P2, START)
    segundo = calculate_sla_targets(policy, ServiceCasePriority.P2, START)
    assert primeiro == segundo


@pytest.mark.parametrize('priority', list(ServiceCasePriority))
def test_sla_usa_fator_inteiro_por_prioridade(policy: SlaPolicy, priority: ServiceCasePriority):
    alvo = calculate_sla_targets(policy, priority, START)
    fator = PRIORITY_SLA_FACTOR[priority]
    assert alvo.response_due_at == START + timedelta(minutes=30 * fator)
    assert alvo.resolution_due_at == START + timedelta(minutes=240 * fator)


def test_prioridade_maior_tem_prazo_menor_ou_igual(policy: SlaPolicy):
    prazos = [
        calculate_sla_targets(policy, priority, START).resolution_due_at
        for priority in (
            ServiceCasePriority.P1,
            ServiceCasePriority.P2,
            ServiceCasePriority.P3,
            ServiceCasePriority.P4,
        )
    ]
    assert prazos == sorted(prazos)


def test_politica_inativa_nao_produz_prazo():
    inativa = SlaPolicy(
        policy_id=str(uuid4()),
        name='Inativa',
        response_minutes=30,
        resolution_minutes=240,
        active=False,
    )
    with pytest.raises(SlaViolationError, match='inativa'):
        calculate_sla_targets(inativa, ServiceCasePriority.P1, START)


def test_started_at_sem_timezone_e_rejeitado(policy: SlaPolicy):
    with pytest.raises(SlaViolationError, match='timezone'):
        calculate_sla_targets(policy, ServiceCasePriority.P1, datetime(2026, 9, 19, 12, 0))


def test_prioridade_fora_do_contrato_e_rejeitada(policy: SlaPolicy):
    with pytest.raises(SlaViolationError, match='priority'):
        calculate_sla_targets(policy, 'P1', START)


# --- avaliação de SLA e manipulação de relógio ----------------------------


@pytest.fixture
def targets(policy: SlaPolicy) -> SlaTargets:
    return calculate_sla_targets(policy, ServiceCasePriority.P1, START)


def test_dentro_do_prazo(targets: SlaTargets):
    assert evaluate_sla(targets, evaluated_at=START + timedelta(minutes=10)) is SlaState.ON_TIME


def test_resposta_estourada_sem_primeira_resposta(targets: SlaTargets):
    estado = evaluate_sla(targets, evaluated_at=START + timedelta(minutes=31))
    assert estado is SlaState.RESPONSE_BREACHED


def test_resposta_dentro_do_prazo_nao_estoura_depois(targets: SlaTargets):
    estado = evaluate_sla(
        targets,
        evaluated_at=START + timedelta(minutes=120),
        first_response_at=START + timedelta(minutes=5),
    )
    assert estado is SlaState.ON_TIME


def test_resolucao_estourada_tem_precedencia(targets: SlaTargets):
    estado = evaluate_sla(
        targets,
        evaluated_at=START + timedelta(minutes=500),
        first_response_at=START + timedelta(minutes=500),
    )
    assert estado is SlaState.RESOLUTION_BREACHED


def test_resolucao_dentro_do_prazo_congela_o_estado(targets: SlaTargets):
    estado = evaluate_sla(
        targets,
        evaluated_at=START + timedelta(days=30),
        first_response_at=START + timedelta(minutes=5),
        resolved_at=START + timedelta(minutes=100),
    )
    assert estado is SlaState.ON_TIME


def test_instante_de_avaliacao_anterior_ao_inicio_e_rejeitado(targets: SlaTargets):
    with pytest.raises(SlaViolationError, match='evaluated_at'):
        evaluate_sla(targets, evaluated_at=START - timedelta(minutes=1))


def test_marco_anterior_ao_inicio_e_rejeitado(targets: SlaTargets):
    with pytest.raises(SlaViolationError, match='first_response_at'):
        evaluate_sla(
            targets,
            evaluated_at=START + timedelta(minutes=10),
            first_response_at=START - timedelta(minutes=1),
        )


def test_resolucao_anterior_a_primeira_resposta_e_rejeitada(targets: SlaTargets):
    with pytest.raises(SlaViolationError, match='resolved_at'):
        evaluate_sla(
            targets,
            evaluated_at=START + timedelta(minutes=60),
            first_response_at=START + timedelta(minutes=30),
            resolved_at=START + timedelta(minutes=10),
        )


def test_instante_sem_timezone_e_rejeitado(targets: SlaTargets):
    with pytest.raises(SlaViolationError, match='timezone'):
        evaluate_sla(targets, evaluated_at=datetime(2026, 9, 19, 13, 0))


def test_prazos_incoerentes_sao_rejeitados():
    with pytest.raises(SlaViolationError, match='response_due_at'):
        SlaTargets(
            policy_id=str(uuid4()),
            priority=ServiceCasePriority.P1,
            started_at=START,
            response_due_at=START,
            resolution_due_at=START + timedelta(minutes=10),
        )
    with pytest.raises(SlaViolationError, match='resolution_due_at'):
        SlaTargets(
            policy_id=str(uuid4()),
            priority=ServiceCasePriority.P1,
            started_at=START,
            response_due_at=START + timedelta(minutes=30),
            resolution_due_at=START + timedelta(minutes=10),
        )


# --- portão de aprovação --------------------------------------------------


def test_transicao_sob_portao_e_identificada():
    assert requires_approval(ServiceCaseState.PENDING_APPROVAL, ServiceCaseState.IN_PROGRESS)
    assert not requires_approval(ServiceCaseState.TRIAGE, ServiceCaseState.IN_PROGRESS)
    assert not requires_approval(ServiceCaseState.PENDING_APPROVAL, ServiceCaseState.CANCELED)


def test_sem_aprovacao_a_transicao_e_bloqueada():
    with pytest.raises(ApprovalRequiredError, match='APPROVED'):
        assert_approval_allows_transition(
            ServiceCaseState.PENDING_APPROVAL, ServiceCaseState.IN_PROGRESS, ()
        )


def test_aprovacao_pendente_nao_libera():
    with pytest.raises(ApprovalRequiredError):
        assert_approval_allows_transition(
            ServiceCaseState.PENDING_APPROVAL,
            ServiceCaseState.IN_PROGRESS,
            (ApprovalStatus.PENDING,),
        )


def test_rejeicao_isolada_nao_libera():
    with pytest.raises(ApprovalRequiredError):
        assert_approval_allows_transition(
            ServiceCaseState.PENDING_APPROVAL,
            ServiceCaseState.IN_PROGRESS,
            (ApprovalStatus.REJECTED,),
        )


def test_aprovacao_valida_libera_mesmo_com_rejeicao_no_historico():
    assert_approval_allows_transition(
        ServiceCaseState.PENDING_APPROVAL,
        ServiceCaseState.IN_PROGRESS,
        (ApprovalStatus.REJECTED, ApprovalStatus.APPROVED),
    )


def test_transicao_fora_do_portao_nao_exige_aprovacao():
    assert_approval_allows_transition(
        ServiceCaseState.TRIAGE, ServiceCaseState.IN_PROGRESS, ()
    )


def test_decisao_e_terminal():
    validate_approval_decision(ApprovalStatus.PENDING, ApprovalStatus.APPROVED)
    validate_approval_decision(ApprovalStatus.PENDING, ApprovalStatus.REJECTED)
    with pytest.raises(ServiceManagementValidationError, match='APPROVED ou REJECTED'):
        validate_approval_decision(ApprovalStatus.PENDING, ApprovalStatus.PENDING)
    with pytest.raises(ServiceManagementValidationError, match='já decidida'):
        validate_approval_decision(ApprovalStatus.REJECTED, ApprovalStatus.APPROVED)


# --- atribuição -----------------------------------------------------------


def _change(**overrides):
    payload = {
        'case_id': str(uuid4()),
        'assignment_group': 'Sustentacao',
        'assignee': 'ana',
        'current_group': None,
        'current_assignee': None,
        'correlation_id': 'corr-1',
    }
    payload.update(overrides)
    return plan_assignment(**payload)


def test_atribuicao_registra_estado_anterior():
    mudanca = _change(current_group='Triagem', current_assignee='bruno')
    assert mudanca.previous_group == 'Triagem'
    assert mudanca.previous_assignee == 'bruno'
    assert mudanca.is_noop is False


def test_reatribuicao_identica_e_noop():
    assert _change(current_group='Sustentacao', current_assignee='ana').is_noop is True


def test_troca_apenas_de_responsavel_nao_e_noop():
    assert _change(current_group='Sustentacao', current_assignee='bruno').is_noop is False


def test_grupo_obrigatorio():
    with pytest.raises(AssignmentValidationError, match='assignment_group'):
        _change(assignment_group='   ')


def test_responsavel_e_opcional():
    assert _change(assignee=None).assignee is None
    assert _change(assignee='  ').assignee is None


def test_valores_sao_normalizados():
    mudanca = _change(assignment_group='  Sustentacao  ', assignee='  ana  ')
    assert mudanca.assignment_group == 'Sustentacao'
    assert mudanca.assignee == 'ana'
