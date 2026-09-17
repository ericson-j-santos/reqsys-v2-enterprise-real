"""Testes do plano de controle da Central: roteador, WIP e Evidence Ledger."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import central
from app.application.services.central_service import (
    CentralService,
    InvalidTransitionError,
    WorkRequestNotFoundError,
)
from app.domain.central.evidence_ledger import (
    CheckResult,
    EvidenceCheck,
    EvidenceLedger,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.executor_router import ExecutorRouter
from app.domain.central.models import (
    Environment,
    ExecutorKind,
    Priority,
    WorkRequest,
    WorkRequestInput,
    WorkRequestStatus,
)
from app.domain.central.wip_policy import WipPolicy

SHA_A = "a" * 40
SHA_B = "b" * 40


def entrada(**overrides) -> WorkRequestInput:
    base = {
        "title": "Corrigir workflow de smoke",
        "project": "reqsys",
        "root_cause_id": "rc-ci-smoke",
        "correlation_id": "corr-12345678",
        "signals": ["pipeline vermelho"],
    }
    base.update(overrides)
    return WorkRequestInput(**base)


# --------------------------------------------------------------------------- #
# Executor Router
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("titulo", "sinais", "esperado", "regra"),
    [
        ("Reparar workflow de CI", [], ExecutorKind.CI_REPAIR, "ci.repair"),
        ("Sincronizar Planner com Teams", [], ExecutorKind.GRAPH, "microsoft.graph"),
        ("Ajustar stored procedure", ["SQL Server"], ExecutorKind.SQL, "data.sql"),
        ("Publicar artefato no Google Drive", [], ExecutorKind.DRIVE, "artifact.drive"),
        ("Executar script via Command Gateway", [], ExecutorKind.COMMAND_GATEWAY, "desktop.command_gateway"),
        ("Abrir pull request de correcao", [], ExecutorKind.GITHUB, "scm.github"),
        ("Atualizar README do runtime", [], ExecutorKind.DOCS, "docs"),
    ],
)
def test_router_classifica_por_regra_deterministica(titulo, sinais, esperado, regra):
    decisao = ExecutorRouter().route(entrada(title=titulo, signals=sinais))
    assert decisao.executor is esperado
    assert decisao.rule_id == regra
    assert decisao.requires_human is False


def test_router_prioriza_bloqueio_de_identidade_sobre_executor_tecnico():
    decisao = ExecutorRouter().route(
        entrada(title="Corrigir workflow de CI do Graph", signals=["falta admin consent"])
    )
    assert decisao.executor is ExecutorKind.HUMAN_GATE
    assert decisao.rule_id == "identity.blocked"
    assert decisao.human_reason == "identity_or_permission_missing"


def test_router_sem_regra_correspondente_vai_para_human_gate():
    decisao = ExecutorRouter().route(entrada(title="Solicitacao generica", signals=[]))
    assert decisao.executor is ExecutorKind.HUMAN_GATE
    assert decisao.rule_id == "unclassified"


def test_router_nao_casa_termo_curto_dentro_de_palavra():
    """Controle negativo: 'ci' não pode casar com 'precificacao'."""
    decisao = ExecutorRouter().route(entrada(title="Revisar precificacao do contrato", signals=[]))
    assert decisao.rule_id == "unclassified"


def test_router_ignora_acentos_e_pontuacao():
    decisao = ExecutorRouter().route(entrada(title="Falha no CI/CD", signals=[]))
    assert decisao.executor is ExecutorKind.CI_REPAIR


# --------------------------------------------------------------------------- #
# WIP por causa raiz
# --------------------------------------------------------------------------- #


def _request(request_id: str, root_cause: str, priority: Priority, minutos: int, status=WorkRequestStatus.RECEIVED):
    momento = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutos)
    return WorkRequest(
        request_id=request_id,
        title=request_id,
        project="reqsys",
        environment=Environment.DEV,
        priority=priority,
        root_cause_id=root_cause,
        correlation_id="corr-12345678",
        executor=ExecutorKind.CI_REPAIR,
        routing_rule="ci.repair",
        status=status,
        created_at=momento,
        updated_at=momento,
    )


def test_wip_admite_no_maximo_o_limite_de_causas_raiz():
    requests = [
        _request("r1", "rc-a", Priority.P0, 0),
        _request("r2", "rc-b", Priority.P1, 1),
        _request("r3", "rc-c", Priority.P1, 2),
        _request("r4", "rc-d", Priority.P0, 3),
    ]
    plano = WipPolicy(max_active_root_causes=2).plan(requests)
    assert [slot.root_cause_id for slot in plano.admitted] == ["rc-a", "rc-d"]
    assert [slot.root_cause_id for slot in plano.queued] == ["rc-b", "rc-c"]
    assert plano.wip_breach is False


def test_wip_agrupa_multiplos_sintomas_da_mesma_causa_em_uma_vaga():
    requests = [
        _request("r1", "rc-a", Priority.P1, 0),
        _request("r2", "rc-a", Priority.P0, 1),
        _request("r3", "rc-b", Priority.P2, 2),
    ]
    plano = WipPolicy(max_active_root_causes=1).plan(requests)
    assert len(plano.admitted) == 1
    assert plano.admitted[0].root_cause_id == "rc-a"
    # A causa herda a maior prioridade entre seus sintomas.
    assert plano.admitted[0].priority is Priority.P0
    assert set(plano.admitted[0].request_ids) == {"r1", "r2"}


def test_wip_preserva_vaga_de_causa_ja_em_andamento():
    requests = [
        _request("r1", "rc-em-andamento", Priority.P3, 10, status=WorkRequestStatus.EXECUTING),
        _request("r2", "rc-nova-p0", Priority.P0, 0),
    ]
    plano = WipPolicy(max_active_root_causes=1).plan(requests)
    assert [slot.root_cause_id for slot in plano.admitted] == ["rc-em-andamento"]
    assert [slot.root_cause_id for slot in plano.queued] == ["rc-nova-p0"]


def test_wip_sinaliza_violacao_quando_ativas_excedem_o_limite():
    requests = [
        _request("r1", "rc-a", Priority.P1, 0, status=WorkRequestStatus.EXECUTING),
        _request("r2", "rc-b", Priority.P1, 1, status=WorkRequestStatus.EXECUTING),
    ]
    plano = WipPolicy(max_active_root_causes=1).plan(requests)
    assert plano.wip_breach is True
    assert len(plano.admitted) == 2  # trabalho iniciado não é abandonado
    assert plano.queued == ()


def test_wip_ignora_solicitacoes_terminais():
    requests = [
        _request("r1", "rc-a", Priority.P0, 0, status=WorkRequestStatus.EVIDENCED),
        _request("r2", "rc-b", Priority.P2, 1),
    ]
    plano = WipPolicy(max_active_root_causes=3).plan(requests)
    assert [slot.root_cause_id for slot in plano.admitted] == ["rc-b"]


# --------------------------------------------------------------------------- #
# Evidence Ledger
# --------------------------------------------------------------------------- #


def _evidencia(sha=SHA_A, **checks) -> EvidenceRecordInput:
    return EvidenceRecordInput(
        request_id="WR-1",
        sha=sha,
        environment=Environment.DEV,
        checks={EvidenceCheck(k): CheckResult(v) for k, v in checks.items()},
    )


def test_ledger_exige_as_quatro_verificacoes_para_evidenciar():
    ledger = EvidenceLedger()
    parcial = ledger.registrar(_evidencia(positive="PASS", idempotency="PASS"))
    assert parcial.status is EvidenceStatus.PARTIAL
    assert set(parcial.missing_checks) == {EvidenceCheck.NEGATIVE_CONTROL, EvidenceCheck.INDEPENDENT_READ}

    completo = ledger.registrar(_evidencia(negative_control="PASS", independent_read="PASS"))
    assert completo.status is EvidenceStatus.EVIDENCED
    assert completo.missing_checks == ()


def test_ledger_bloqueia_quando_qualquer_verificacao_falha():
    ledger = EvidenceLedger()
    registro = ledger.registrar(
        _evidencia(
            positive="PASS",
            negative_control="FAIL",
            idempotency="PASS",
            independent_read="PASS",
        )
    )
    assert registro.status is EvidenceStatus.BLOCKED


def test_ledger_sem_verificacao_aprovada_fica_nao_validado():
    ledger = EvidenceLedger()
    assert ledger.registrar(_evidencia(positive="PENDING")).status is EvidenceStatus.NOT_VALIDATED


def test_ledger_invalida_evidencia_ao_mudar_de_sha():
    ledger = EvidenceLedger()
    ledger.registrar(
        _evidencia(
            positive="PASS", negative_control="PASS", idempotency="PASS", independent_read="PASS"
        )
    )
    assert ledger.status_para("WR-1", SHA_A) is EvidenceStatus.EVIDENCED

    novo = ledger.registrar(_evidencia(sha=SHA_B, positive="PASS"))
    assert novo.status is EvidenceStatus.PARTIAL
    assert ledger.status_para("WR-1", SHA_B) is EvidenceStatus.PARTIAL

    historico = ledger.historico("WR-1")
    assert historico[0].status is EvidenceStatus.SUPERSEDED
    assert historico[0].superseded_by_sha == SHA_B


def test_ledger_nao_reaproveita_evidencia_de_outro_sha():
    ledger = EvidenceLedger()
    ledger.registrar(
        _evidencia(
            positive="PASS", negative_control="PASS", idempotency="PASS", independent_read="PASS"
        )
    )
    assert ledger.status_para("WR-1", SHA_B) is EvidenceStatus.NOT_VALIDATED


def test_ledger_sem_registro_e_nao_validado():
    assert EvidenceLedger().status_para("inexistente", SHA_A) is EvidenceStatus.NOT_VALIDATED


# --------------------------------------------------------------------------- #
# Serviço: ciclo completo
# --------------------------------------------------------------------------- #


async def test_registro_e_idempotente_por_identidade_da_solicitacao():
    service = CentralService()
    primeira = await service.registrar(entrada())
    segunda = await service.registrar(entrada())
    assert primeira.request_id == segunda.request_id
    assert len(await service.listar()) == 1


async def test_solicitacao_com_bloqueio_humano_nasce_bloqueada_e_fora_da_fila_executavel():
    service = CentralService()
    solicitacao = await service.registrar(
        entrada(title="Conceder admin consent no Graph", signals=["consentimento pendente"])
    )
    assert solicitacao.status is WorkRequestStatus.BLOCKED
    assert solicitacao.executor is ExecutorKind.HUMAN_GATE
    assert solicitacao.blocker and solicitacao.next_action
    assert await service.proximo_item() is None


async def test_proximo_item_respeita_wip_e_filtra_por_executor():
    service = CentralService(wip_policy=WipPolicy(max_active_root_causes=1))
    await service.registrar(entrada(title="Reparar workflow de CI", root_cause_id="rc-ci"))
    await service.registrar(
        entrada(title="Sincronizar Planner com Teams", root_cause_id="rc-graph", correlation_id="corr-87654321")
    )

    proximo = await service.proximo_item()
    assert proximo is not None and proximo.executor is ExecutorKind.CI_REPAIR
    # A segunda causa raiz não tem vaga, logo não há item para o executor Graph.
    assert await service.proximo_item(ExecutorKind.GRAPH) is None


async def test_ciclo_completo_ate_evidenciado():
    service = CentralService()
    solicitacao = await service.registrar(entrada(sha=SHA_A))
    await service.aplicar_admissao()
    await service.transicionar(solicitacao.request_id, WorkRequestStatus.EXECUTING)

    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=solicitacao.request_id,
            sha=SHA_A,
            environment=Environment.DEV,
            checks={
                EvidenceCheck.POSITIVE: CheckResult.PASS,
                EvidenceCheck.NEGATIVE_CONTROL: CheckResult.PASS,
                EvidenceCheck.IDEMPOTENCY: CheckResult.PASS,
                EvidenceCheck.INDEPENDENT_READ: CheckResult.PASS,
            },
        )
    )
    final = await service.transicionar(solicitacao.request_id, WorkRequestStatus.EVIDENCED)
    assert final.status is WorkRequestStatus.EVIDENCED


async def test_conclusao_sem_evidencia_completa_e_recusada():
    service = CentralService()
    solicitacao = await service.registrar(entrada(sha=SHA_A))
    await service.aplicar_admissao()
    await service.transicionar(solicitacao.request_id, WorkRequestStatus.EXECUTING)
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=solicitacao.request_id,
            sha=SHA_A,
            environment=Environment.DEV,
            checks={EvidenceCheck.POSITIVE: CheckResult.PASS},
        )
    )
    with pytest.raises(InvalidTransitionError, match="EVIDENCED no SHA corrente"):
        await service.transicionar(solicitacao.request_id, WorkRequestStatus.EVIDENCED)


async def test_conclusao_recusada_quando_evidencia_e_de_outro_sha():
    service = CentralService()
    solicitacao = await service.registrar(entrada(sha=SHA_A))
    await service.aplicar_admissao()
    await service.transicionar(solicitacao.request_id, WorkRequestStatus.EXECUTING)
    checks = {check: CheckResult.PASS for check in EvidenceCheck}
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=solicitacao.request_id, sha=SHA_A, environment=Environment.DEV, checks=checks
        )
    )
    # O trabalho avançou: novo SHA invalida a evidência anterior.
    await service.registrar_evidencia(
        EvidenceRecordInput(
            request_id=solicitacao.request_id,
            sha=SHA_B,
            environment=Environment.DEV,
            checks={EvidenceCheck.POSITIVE: CheckResult.PASS},
        )
    )
    with pytest.raises(InvalidTransitionError):
        await service.transicionar(solicitacao.request_id, WorkRequestStatus.EVIDENCED)


async def test_transicao_invalida_e_recusada():
    service = CentralService()
    solicitacao = await service.registrar(entrada())
    with pytest.raises(InvalidTransitionError):
        await service.transicionar(solicitacao.request_id, WorkRequestStatus.EVIDENCED)


async def test_evidencia_para_solicitacao_inexistente():
    service = CentralService()
    with pytest.raises(WorkRequestNotFoundError):
        await service.registrar_evidencia(
            EvidenceRecordInput(
                request_id="WR-INEXISTENTE",
                sha=SHA_A,
                environment=Environment.DEV,
                checks={EvidenceCheck.POSITIVE: CheckResult.PASS},
            )
        )


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.fixture
def service() -> CentralService:
    return CentralService(wip_policy=WipPolicy(max_active_root_causes=1))


@pytest.fixture
def client(service) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[central.get_central_service] = lambda: service
    app.include_router(central.router)
    return TestClient(app)


def test_api_registra_classifica_e_devolve_correlation_id(client):
    resposta = client.post("/api/central/work-requests", json=entrada().model_dump(mode="json"))
    assert resposta.status_code == 201
    assert resposta.headers["x-correlation-id"] == "corr-12345678"
    corpo = resposta.json()
    assert corpo["executor"] == "ci_repair"
    assert corpo["routing_rule"] == "ci.repair"


def test_api_next_devolve_204_quando_nao_ha_item_executavel(client):
    assert client.get("/api/central/next").status_code == 204


def test_api_plano_de_admissao_enfileira_causa_excedente(client):
    client.post("/api/central/work-requests", json=entrada().model_dump(mode="json"))
    client.post(
        "/api/central/work-requests",
        json=entrada(
            title="Sincronizar Planner com Teams",
            root_cause_id="rc-graph",
            correlation_id="corr-87654321",
        ).model_dump(mode="json"),
    )
    plano = client.get("/api/central/admission-plan").json()
    assert plano["max_active_root_causes"] == 1
    assert len(plano["admitted"]) == 1
    assert len(plano["queued"]) == 1
    assert plano["wip_breach"] is False


def test_api_conclusao_sem_evidencia_retorna_409(client):
    criada = client.post(
        "/api/central/work-requests", json=entrada(sha=SHA_A).model_dump(mode="json")
    ).json()
    client.get("/api/central/next")
    client.post(
        f"/api/central/work-requests/{criada['request_id']}/transition",
        json={"status": "EXECUTING"},
    )
    resposta = client.post(
        f"/api/central/work-requests/{criada['request_id']}/transition",
        json={"status": "EVIDENCED"},
    )
    assert resposta.status_code == 409


def test_api_evidencia_ausente_retorna_404(client):
    assert client.get("/api/central/evidence/WR-INEXISTENTE").status_code == 404


def test_api_solicitacao_inexistente_retorna_404(client):
    assert client.get("/api/central/work-requests/WR-INEXISTENTE").status_code == 404
