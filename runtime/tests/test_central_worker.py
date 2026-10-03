"""Testes do worker da Central e do executor HTTP.

O foco é a invariante que dá sentido ao incremento: o executor produz efeito,
mas **não decide sozinho** que o trabalho está concluído. Só evidência completa
no SHA corrente leva a `EVIDENCED`.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.application.services.central_service import CentralService
from app.application.services.central_worker import (
    CentralWorker,
    CicloResultado,
)
from app.domain.central.evidence_ledger import CheckResult, EvidenceCheck, EvidenceStatus
from app.domain.central.execution import ExecutionOutcome, ExecutionResult
from app.domain.central.models import ExecutorKind, WorkRequestInput, WorkRequestStatus
from app.infrastructure.executors.http_executor import HttpExecutorAdapter, HttpExecutorEndpoint
from app.infrastructure.executors.registry import ExecutorRegistry, registry_de_configuracao

SHA = "a" * 40
TODOS_PASS = {check: CheckResult.PASS for check in EvidenceCheck}


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


class AdaptadorFake:
    """Executor controlável, para exercitar cada desfecho do ciclo."""

    def __init__(self, resultado: ExecutionResult) -> None:
        self.resultado = resultado
        self.chamadas: list[str] = []

    async def executar(self, solicitacao):
        self.chamadas.append(solicitacao.request_id)
        return self.resultado


def registry_com(resultado: ExecutionResult, kind=ExecutorKind.CI_REPAIR):
    adaptador = AdaptadorFake(resultado)
    return ExecutorRegistry({kind: adaptador}), adaptador


# --------------------------------------------------------------------------- #
# Ciclo do worker
# --------------------------------------------------------------------------- #


async def test_ciclo_ocioso_quando_nao_ha_item():
    worker = CentralWorker(CentralService(), ExecutorRegistry())
    relatorio = await worker.executar_um_ciclo()
    assert relatorio.resultado is CicloResultado.OCIOSO


async def test_ciclo_conclui_com_evidencia_completa():
    central = CentralService()
    criada = await central.registrar(entrada())
    registry, adaptador = registry_com(
        ExecutionResult(outcome=ExecutionOutcome.SUCCESS, checks=dict(TODOS_PASS))
    )

    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.EVIDENCIADO
    assert adaptador.chamadas == [criada.request_id]
    final = await central.obter(criada.request_id)
    assert final.status is WorkRequestStatus.EVIDENCED
    assert (await central.obter_evidencia(criada.request_id)).status is EvidenceStatus.EVIDENCED


async def test_ciclo_nao_conclui_com_evidencia_parcial():
    """O executor rodou, mas não comprovou tudo: não pode virar concluído."""
    central = CentralService()
    criada = await central.registrar(entrada())
    registry, _ = registry_com(
        ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            checks={EvidenceCheck.POSITIVE: CheckResult.PASS},
        )
    )

    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.AGUARDANDO_EVIDENCIA
    assert relatorio.evidence_status is EvidenceStatus.PARTIAL
    assert set(relatorio.verificacoes_pendentes) == {
        EvidenceCheck.NEGATIVE_CONTROL,
        EvidenceCheck.IDEMPOTENCY,
        EvidenceCheck.INDEPENDENT_READ,
    }
    final = await central.obter(criada.request_id)
    assert final.status is WorkRequestStatus.AWAITING_EVIDENCE


async def test_ciclo_bloqueia_quando_executor_nao_configurado():
    central = CentralService()
    criada = await central.registrar(entrada())

    relatorio = await CentralWorker(central, ExecutorRegistry()).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.BLOQUEADO
    assert relatorio.blocker == "executor_nao_configurado:ci_repair"
    final = await central.obter(criada.request_id)
    assert final.status is WorkRequestStatus.BLOCKED
    assert final.next_action and "CENTRAL_EXECUTOR_ENDPOINTS" in final.next_action


async def test_ciclo_bloqueia_com_causa_quando_executor_falha():
    central = CentralService()
    criada = await central.registrar(entrada())
    registry, _ = registry_com(
        ExecutionResult(
            outcome=ExecutionOutcome.FAILED,
            blocker="executor_http_indisponivel",
            next_action="Verificar o endpoint.",
        )
    )

    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.BLOQUEADO
    final = await central.obter(criada.request_id)
    assert final.status is WorkRequestStatus.BLOCKED
    assert final.blocker == "executor_http_indisponivel"


async def test_ciclo_registra_verificacao_reprovada_no_ledger():
    central = CentralService()
    criada = await central.registrar(entrada())
    registry, _ = registry_com(
        ExecutionResult(
            outcome=ExecutionOutcome.FAILED,
            checks={EvidenceCheck.IDEMPOTENCY: CheckResult.FAIL},
            blocker="verificacoes_reprovadas:idempotency",
            next_action="Corrigir o executor.",
        )
    )

    await CentralWorker(central, registry).executar_um_ciclo()

    registro = await central.obter_evidencia(criada.request_id)
    assert registro is not None and registro.status is EvidenceStatus.BLOCKED


async def test_excecao_do_executor_vira_bloqueio_e_nao_derruba_o_ciclo():
    class AdaptadorQueExplode:
        async def executar(self, solicitacao):
            raise RuntimeError("falha inesperada")

    central = CentralService()
    criada = await central.registrar(entrada())
    registry = ExecutorRegistry({ExecutorKind.CI_REPAIR: AdaptadorQueExplode()})

    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.BLOQUEADO
    assert relatorio.blocker == "executor_excecao:RuntimeError"
    assert (await central.obter(criada.request_id)).status is WorkRequestStatus.BLOCKED


async def test_human_gate_nunca_e_executado():
    central = CentralService()
    await central.registrar(
        entrada(title="Conceder admin consent no Graph", signals=["consentimento pendente"])
    )
    registry, adaptador = registry_com(
        ExecutionResult(outcome=ExecutionOutcome.SUCCESS, checks=dict(TODOS_PASS)),
        kind=ExecutorKind.CI_REPAIR,
    )

    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.OCIOSO
    assert adaptador.chamadas == []


async def test_ciclo_filtra_por_executor():
    central = CentralService()
    await central.registrar(entrada(title="Reparar workflow de CI", root_cause_id="rc-ci"))
    registry, adaptador = registry_com(
        ExecutionResult(outcome=ExecutionOutcome.SUCCESS, checks=dict(TODOS_PASS)),
        kind=ExecutorKind.GRAPH,
    )

    relatorio = await CentralWorker(central, registry).executar_um_ciclo(ExecutorKind.GRAPH)

    assert relatorio.resultado is CicloResultado.OCIOSO
    assert adaptador.chamadas == []


# --------------------------------------------------------------------------- #
# Executor HTTP
# --------------------------------------------------------------------------- #


class ExecutorStub:
    """Endpoint de executor que cumpre o contrato, com defeitos configuráveis."""

    def __init__(self, duplicar_efeito=False, leitura_divergente=False, recusa_probe=True):
        self.efeitos: dict[str, str] = {}
        self.duplicar_efeito = duplicar_efeito
        self.leitura_divergente = leitura_divergente
        self.recusa_probe = recusa_probe
        self.posts = 0

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            effect_id = request.url.params.get("effect_id", "")
            devolvido = "outro-efeito" if self.leitura_divergente else effect_id
            return httpx.Response(200, json={"effect_id": devolvido, "confirmed": True})

        self.posts += 1
        corpo = json.loads(request.content)
        chave = corpo.get("idempotency_key")
        if not chave or not corpo.get("request_id"):
            # Controle negativo: carga inválida tem de ser recusada.
            return httpx.Response(400 if self.recusa_probe else 200, json={"accepted": False})

        duplicado = chave in self.efeitos
        if duplicado and self.duplicar_efeito:
            self.efeitos[chave] = f"efeito-{self.posts}"  # defeito: cria outro efeito
            duplicado = False
        elif not duplicado:
            self.efeitos[chave] = f"efeito-{self.posts}"

        effect_id = self.efeitos[chave]
        return httpx.Response(
            200,
            json={
                "accepted": True,
                "effect_id": effect_id,
                "duplicate_effect": duplicado,
                "verification_url": f"https://executor.local/verificar?effect_id={effect_id}",
                "evidence_run_url": "https://executor.local/run/1",
            },
        )


def adaptador_http(stub: ExecutorStub, com_probe=True) -> HttpExecutorAdapter:
    return HttpExecutorAdapter(
        HttpExecutorEndpoint(
            url="https://executor.local/executar",
            negative_probe={"sha": "invalido"} if com_probe else None,
        ),
        transport=httpx.MockTransport(stub.handler),
    )


async def _solicitacao(central: CentralService, **kw):
    criada = await central.registrar(entrada(**kw))
    await central.aplicar_admissao()
    return criada


async def test_http_executor_comprova_as_quatro_verificacoes():
    central = CentralService()
    criada = await _solicitacao(central)
    resultado = await adaptador_http(ExecutorStub()).executar(criada)

    assert resultado.outcome is ExecutionOutcome.SUCCESS
    assert resultado.checks == TODOS_PASS
    assert resultado.evidence_run_url == "https://executor.local/run/1"


async def test_http_executor_sem_probe_deixa_controle_negativo_pendente():
    """Sem controle negativo declarado, a evidência não pode ficar completa."""
    central = CentralService()
    criada = await _solicitacao(central)
    resultado = await adaptador_http(ExecutorStub(), com_probe=False).executar(criada)

    assert resultado.outcome is ExecutionOutcome.SUCCESS
    assert EvidenceCheck.NEGATIVE_CONTROL not in resultado.checks
    assert resultado.verificacoes_pendentes == (EvidenceCheck.NEGATIVE_CONTROL,)


async def test_http_executor_reprova_idempotencia_quando_replay_cria_outro_efeito():
    central = CentralService()
    criada = await _solicitacao(central)
    resultado = await adaptador_http(ExecutorStub(duplicar_efeito=True)).executar(criada)

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.checks[EvidenceCheck.IDEMPOTENCY] is CheckResult.FAIL
    assert resultado.blocker == "verificacoes_reprovadas:idempotency"


async def test_http_executor_reprova_leitura_independente_divergente():
    central = CentralService()
    criada = await _solicitacao(central)
    resultado = await adaptador_http(ExecutorStub(leitura_divergente=True)).executar(criada)

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.checks[EvidenceCheck.INDEPENDENT_READ] is CheckResult.FAIL


async def test_http_executor_reprova_quando_probe_invalido_e_aceito():
    """Se o executor aceita carga inválida, o controle negativo reprova."""
    central = CentralService()
    criada = await _solicitacao(central)
    resultado = await adaptador_http(ExecutorStub(recusa_probe=False)).executar(criada)

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.checks[EvidenceCheck.NEGATIVE_CONTROL] is CheckResult.FAIL


async def test_http_executor_bloqueia_solicitacao_sem_sha():
    central = CentralService()
    criada = await _solicitacao(central, sha=None)
    resultado = await adaptador_http(ExecutorStub()).executar(criada)

    assert resultado.outcome is ExecutionOutcome.BLOCKED
    assert resultado.blocker == "solicitacao_sem_sha"


async def test_http_executor_trata_indisponibilidade_como_falha_acionavel():
    async def indisponivel(_request):
        raise httpx.ConnectError("conexão recusada")

    central = CentralService()
    criada = await _solicitacao(central)
    adaptador = HttpExecutorAdapter(
        HttpExecutorEndpoint(url="https://executor.local/executar"),
        transport=httpx.MockTransport(indisponivel),
    )
    resultado = await adaptador.executar(criada)

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.blocker == "executor_http_indisponivel"


async def test_http_executor_usa_mesma_chave_de_idempotencia_para_mesmo_sha():
    central = CentralService()
    criada = await _solicitacao(central)
    stub = ExecutorStub()
    await adaptador_http(stub).executar(criada)
    await adaptador_http(stub).executar(criada)

    # Quatro POSTs válidos (dois por execução), um único efeito.
    assert len(stub.efeitos) == 1


# --------------------------------------------------------------------------- #
# Registro de executores
# --------------------------------------------------------------------------- #


def test_registry_vazio_quando_configuracao_ausente():
    assert registry_de_configuracao("").configurados() == ()


def test_registry_aceita_url_simples_e_objeto():
    registry = registry_de_configuracao(
        json.dumps(
            {
                "ci_repair": "https://executor/ci",
                "graph": {"url": "https://executor/graph", "negative_probe": {"sha": "x"}},
            }
        )
    )
    assert registry.configurados() == (ExecutorKind.CI_REPAIR, ExecutorKind.GRAPH)


def test_registry_recusa_human_gate():
    with pytest.raises(ValueError, match="human_gate"):
        registry_de_configuracao(json.dumps({"human_gate": "https://executor/pessoa"}))


def test_registry_recusa_executor_desconhecido():
    with pytest.raises(ValueError, match="executor desconhecido"):
        registry_de_configuracao(json.dumps({"telepatia": "https://executor/x"}))


def test_registry_recusa_json_invalido():
    with pytest.raises(ValueError, match="não é JSON válido"):
        registry_de_configuracao("{nao json}")


def test_registry_recusa_configuracao_sem_url():
    with pytest.raises(ValueError, match="informe a URL"):
        registry_de_configuracao(json.dumps({"ci_repair": {"negative_probe": {}}}))


def test_resultado_nao_bem_sucedido_exige_causa_e_proxima_acao():
    with pytest.raises(ValueError, match="blocker e next_action"):
        ExecutionResult(outcome=ExecutionOutcome.FAILED)


def test_resultado_bem_sucedido_exige_verificacao():
    with pytest.raises(ValueError, match="ao menos uma verificação"):
        ExecutionResult(outcome=ExecutionOutcome.SUCCESS)


async def test_conclusao_cedida_quando_item_muda_de_estado_no_meio():
    """Corrida entre réplicas na conclusão não pode virar erro do ciclo."""
    central = CentralService()
    criada = await central.registrar(entrada())

    class AdaptadorQueBloqueiaNoMeio:
        """Simula outra réplica bloqueando o item durante a execução."""

        async def executar(self, solicitacao):
            await central.transicionar(
                solicitacao.request_id,
                WorkRequestStatus.BLOCKED,
                blocker="assumido_por_outra_replica",
                next_action="Aguardar o desfecho de quem assumiu.",
            )
            return ExecutionResult(outcome=ExecutionOutcome.SUCCESS, checks=dict(TODOS_PASS))

    registry = ExecutorRegistry({ExecutorKind.CI_REPAIR: AdaptadorQueBloqueiaNoMeio()})
    relatorio = await CentralWorker(central, registry).executar_um_ciclo()

    assert relatorio.resultado is CicloResultado.CEDIDO
    # A evidência produzida não se perde: fica no ledger para quem assumiu.
    assert (await central.obter_evidencia(criada.request_id)).status is EvidenceStatus.EVIDENCED
    assert (await central.obter(criada.request_id)).status is WorkRequestStatus.BLOCKED
