"""Testes das métricas da Central, com foco no Lead Time to Evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import central
from app.application.services.central_service import CentralService
from app.domain.central.evidence_ledger import (
    CheckResult,
    EvidenceCheck,
    EvidenceRecord,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.metrics import calcular_metricas, percentil
from app.domain.central.models import (
    Environment,
    ExecutorKind,
    Priority,
    WorkRequest,
    WorkRequestInput,
    WorkRequestStatus,
)
from app.domain.central.wip_policy import WipPolicy

BASE = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 40
SHA_OUTRO = "b" * 40
TODOS_PASS = {check: CheckResult.PASS for check in EvidenceCheck}


def solicitacao(
    request_id="WR-1",
    status=WorkRequestStatus.RECEIVED,
    root_cause="rc-ci",
    executor=ExecutorKind.CI_REPAIR,
    criada_em=BASE,
    sha=SHA,
    blocker=None,
    next_action=None,
) -> WorkRequest:
    return WorkRequest(
        request_id=request_id,
        title=request_id,
        project="reqsys",
        environment=Environment.DEV,
        priority=Priority.P1,
        root_cause_id=root_cause,
        correlation_id="corr-12345678",
        sha=sha,
        executor=executor,
        routing_rule="ci.repair",
        status=status,
        blocker=blocker,
        next_action=next_action,
        created_at=criada_em,
        updated_at=criada_em,
    )


def evidencia(
    request_id="WR-1",
    status=EvidenceStatus.EVIDENCED,
    registrada_em=BASE + timedelta(seconds=60),
    sha=SHA,
    checks=None,
) -> EvidenceRecord:
    return EvidenceRecord(
        request_id=request_id,
        sha=sha,
        environment=Environment.DEV,
        checks=checks if checks is not None else dict(TODOS_PASS),
        production_touched=False,
        evidence_run_url=None,
        status=status,
        recorded_at=registrada_em,
    )


def metricas(solicitacoes, evidencias=None, limite=3):
    evidencias = evidencias or {}
    return calcular_metricas(solicitacoes, evidencias, WipPolicy(limite).plan(solicitacoes))


# --------------------------------------------------------------------------- #
# Percentil
# --------------------------------------------------------------------------- #


def test_percentil_sem_amostra():
    assert percentil([], 0.5) is None


def test_percentil_com_uma_amostra():
    assert percentil([42.0], 0.95) == 42.0


def test_percentil_interpola():
    assert percentil([0.0, 10.0], 0.5) == 5.0
    assert percentil([0.0, 10.0, 20.0, 30.0], 0.5) == 15.0


# --------------------------------------------------------------------------- #
# Lead Time to Evidence
# --------------------------------------------------------------------------- #


def test_lead_time_mede_da_criacao_ate_a_evidencia():
    resultado = metricas(
        [solicitacao(status=WorkRequestStatus.EVIDENCED)],
        {"WR-1": evidencia(registrada_em=BASE + timedelta(seconds=90))},
    )
    assert resultado.lead_time_to_evidence.amostras == 1
    assert resultado.lead_time_to_evidence.p50_segundos == 90.0
    assert resultado.lead_time_to_evidence.maximo_segundos == 90.0


def test_lead_time_ignora_evidencia_de_outro_sha():
    """Evidência de outro SHA mediria um lead time fictício."""
    resultado = metricas(
        [solicitacao(status=WorkRequestStatus.EVIDENCED, sha=SHA)],
        {"WR-1": evidencia(sha=SHA_OUTRO)},
    )
    assert resultado.lead_time_to_evidence.amostras == 0
    assert resultado.lead_time_to_evidence.p50_segundos is None


def test_lead_time_ignora_solicitacao_nao_concluida():
    resultado = metricas(
        [solicitacao(status=WorkRequestStatus.AWAITING_EVIDENCE)],
        {"WR-1": evidencia(status=EvidenceStatus.PARTIAL)},
    )
    assert resultado.lead_time_to_evidence.amostras == 0


def test_lead_time_com_varias_amostras():
    solicitacoes = [
        solicitacao(f"WR-{i}", status=WorkRequestStatus.EVIDENCED, root_cause=f"rc-{i}")
        for i in range(4)
    ]
    evidencias = {
        f"WR-{i}": evidencia(f"WR-{i}", registrada_em=BASE + timedelta(seconds=(i + 1) * 10))
        for i in range(4)
    }
    resultado = metricas(solicitacoes, evidencias)
    assert resultado.lead_time_to_evidence.amostras == 4
    assert resultado.lead_time_to_evidence.p50_segundos == 25.0
    assert resultado.lead_time_to_evidence.maximo_segundos == 40.0


# --------------------------------------------------------------------------- #
# Séries operacionais
# --------------------------------------------------------------------------- #


def test_agrupa_status_e_executor():
    resultado = metricas(
        [
            solicitacao("WR-1", status=WorkRequestStatus.RECEIVED),
            solicitacao("WR-2", status=WorkRequestStatus.RECEIVED, root_cause="rc-b"),
            solicitacao("WR-3", status=WorkRequestStatus.EXECUTING, executor=ExecutorKind.GRAPH, root_cause="rc-c"),
        ]
    )
    assert resultado.total == 3
    assert resultado.por_status == {"EXECUTING": 1, "RECEIVED": 2}
    assert resultado.por_executor == {"ci_repair": 2, "graph": 1}


def test_bloqueios_agrupados_por_causa_e_nao_por_instancia():
    """Cinco sintomas do mesmo defeito precisam aparecer como uma causa."""
    solicitacoes = [
        solicitacao(
            f"WR-{i}",
            status=WorkRequestStatus.BLOCKED,
            root_cause=f"rc-{i}",
            blocker=f"executor_nao_configurado:{'sql' if i < 3 else 'graph'}",
            next_action="Configurar o executor.",
        )
        for i in range(5)
    ]
    resultado = metricas(solicitacoes)
    assert resultado.bloqueadas == 5
    assert resultado.bloqueios_por_causa == {"executor_nao_configurado": 5}


def test_bloqueio_sem_causa_informada():
    resultado = metricas(
        [
            solicitacao(
                "WR-1",
                status=WorkRequestStatus.BLOCKED,
                blocker="sem_prefixo",
                next_action="Investigar.",
            )
        ]
    )
    assert resultado.bloqueios_por_causa == {"sem_prefixo": 1}


def test_verificacoes_pendentes_mostram_o_que_impede_a_conclusao():
    solicitacoes = [
        solicitacao("WR-1", status=WorkRequestStatus.AWAITING_EVIDENCE),
        solicitacao("WR-2", status=WorkRequestStatus.AWAITING_EVIDENCE, root_cause="rc-b"),
    ]
    evidencias = {
        "WR-1": evidencia("WR-1", status=EvidenceStatus.PARTIAL, checks={EvidenceCheck.POSITIVE: CheckResult.PASS}),
        "WR-2": evidencia(
            "WR-2",
            status=EvidenceStatus.PARTIAL,
            checks={
                EvidenceCheck.POSITIVE: CheckResult.PASS,
                EvidenceCheck.IDEMPOTENCY: CheckResult.PASS,
                EvidenceCheck.INDEPENDENT_READ: CheckResult.PASS,
            },
        ),
    }
    resultado = metricas(solicitacoes, evidencias)
    assert resultado.aguardando_evidencia == 2
    # O controle negativo falta nas duas: é o gargalo de comprovação.
    assert resultado.verificacoes_pendentes["negative_control"] == 2
    assert resultado.verificacoes_pendentes["idempotency"] == 1
    assert resultado.idade_maxima_aguardando_evidencia_segundos is not None


def test_wip_reportado_a_partir_do_plano():
    solicitacoes = [
        solicitacao(f"WR-{i}", root_cause=f"rc-{i}", criada_em=BASE + timedelta(minutes=i))
        for i in range(5)
    ]
    solicitacoes[0] = solicitacao("WR-0", status=WorkRequestStatus.EXECUTING, root_cause="rc-0")
    resultado = metricas(solicitacoes, limite=2)
    assert resultado.max_causas_raiz_ativas == 2
    assert resultado.causas_raiz_ativas == 1
    assert resultado.causas_raiz_enfileiradas == 3
    assert resultado.wip_breach is False


def test_wip_breach_reportado():
    solicitacoes = [
        solicitacao("WR-1", status=WorkRequestStatus.EXECUTING, root_cause="rc-a"),
        solicitacao("WR-2", status=WorkRequestStatus.EXECUTING, root_cause="rc-b"),
    ]
    resultado = metricas(solicitacoes, limite=1)
    assert resultado.wip_breach is True
    assert resultado.causas_raiz_ativas == 2


def test_central_vazia_nao_quebra():
    resultado = metricas([])
    assert resultado.total == 0
    assert resultado.lead_time_to_evidence.amostras == 0
    assert resultado.to_dict()["lead_time_to_evidence"]["p50_segundos"] is None


# --------------------------------------------------------------------------- #
# Serviço e API
# --------------------------------------------------------------------------- #


def entrada(**overrides) -> WorkRequestInput:
    base = {
        "title": "Reparar workflow de CI",
        "project": "reqsys",
        "root_cause_id": "rc-ci",
        "correlation_id": "corr-12345678",
        "signals": ["pipeline vermelho"],
        "sha": SHA,
    }
    base.update(overrides)
    return WorkRequestInput(**base)


async def test_servico_calcula_metricas_do_estado_persistido():
    service = CentralService()
    criada = await service.registrar(entrada())
    await service.aplicar_admissao()
    await service.transicionar(criada.request_id, WorkRequestStatus.EXECUTING)
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=criada.request_id,
            sha=SHA,
            environment=Environment.DEV,
            checks=dict(TODOS_PASS),
        )
    )
    await service.transicionar(criada.request_id, WorkRequestStatus.EVIDENCED)

    resultado = await service.metricas()
    assert resultado.total == 1
    assert resultado.por_status == {"EVIDENCED": 1}
    assert resultado.evidencia_por_status == {"EVIDENCED": 1}
    assert resultado.lead_time_to_evidence.amostras == 1


@pytest.fixture
def client() -> TestClient:
    service = CentralService()
    app = FastAPI()
    app.dependency_overrides[central.get_central_service] = lambda: service
    app.include_router(central.router)
    return TestClient(app)


def test_api_metrics_em_central_vazia(client):
    resposta = client.get("/api/central/metrics")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 0
    assert corpo["wip"]["max_causas_raiz_ativas"] == 3
    assert corpo["lead_time_to_evidence"]["amostras"] == 0


def test_api_metrics_reporta_bloqueio(client):
    client.post(
        "/api/central/work-requests",
        json=entrada(
            title="Conceder admin consent no Graph", signals=["consentimento pendente"]
        ).model_dump(mode="json"),
    )
    corpo = client.get("/api/central/metrics").json()
    assert corpo["bloqueios"]["total"] == 1
    assert corpo["bloqueios"]["por_causa"] == {"identity_or_permission_missing": 1}
    assert corpo["por_executor"] == {"human_gate": 1}
