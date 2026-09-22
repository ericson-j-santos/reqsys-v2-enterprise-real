"""Testes do executor nativo de GitHub Actions.

A API do GitHub é simulada por um stub de transporte que reproduz as respostas
reais (204 sem corpo no dispatch, `workflow_runs` na listagem, 404 para ref
inexistente). O foco é a honestidade das verificações: o adaptador não pode
afirmar idempotência que não verificou, nem concluir sem controle negativo.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.domain.central.evidence_ledger import CheckResult, EvidenceCheck
from app.domain.central.execution import ExecutionOutcome
from app.domain.central.models import (
    Environment,
    ExecutorKind,
    Priority,
    WorkRequest,
    WorkRequestStatus,
)
from app.infrastructure.executors.github_executor import (
    GitHubExecutorAdapter,
    GitHubExecutorConfig,
)
from app.infrastructure.executors.registry import registry_de_configuracao
from datetime import datetime, timezone

SHA = "c" * 40
BASE = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def solicitacao(repository="ericson-j-santos/reqsys-v2-enterprise-real", sha=SHA, branch="main"):
    return WorkRequest(
        request_id="WR-1",
        title="Reparar workflow de CI",
        project="reqsys",
        environment=Environment.DEV,
        priority=Priority.P1,
        root_cause_id="rc-ci",
        correlation_id="corr-12345678",
        repository=repository,
        branch=branch,
        sha=sha,
        executor=ExecutorKind.CI_REPAIR,
        routing_rule="ci.repair",
        status=WorkRequestStatus.ADMITTED,
        created_at=BASE,
        updated_at=BASE,
    )


class GitHubStub:
    """Reproduz o comportamento da API do GitHub relevante ao adaptador."""

    def __init__(self, dispatch_recusa=False, execucao_some=False, sha_divergente=False):
        self.runs: list[dict] = []
        self.dispatches: list[dict] = []
        self.dispatch_recusa = dispatch_recusa
        self.execucao_some = execucao_some
        self.sha_divergente = sha_divergente

    async def handler(self, request: httpx.Request) -> httpx.Response:
        caminho = request.url.path

        if request.method == "POST" and caminho.endswith("/dispatches"):
            corpo = json.loads(request.content)
            self.dispatches.append(corpo)
            if corpo.get("ref") == "refs/heads/inexistente":
                # Ref inexistente: o GitHub recusa.
                return httpx.Response(422, json={"message": "No ref found"})
            if self.dispatch_recusa:
                return httpx.Response(403, json={"message": "Resource not accessible"})
            if not self.execucao_some:
                self.runs.append(
                    {
                        "id": 100 + len(self.runs),
                        "head_sha": corpo["inputs"]["sha"],
                        "event": "workflow_dispatch",
                        "html_url": f"https://github.com/run/{100 + len(self.runs)}",
                    }
                )
            return httpx.Response(204)

        if request.method == "GET" and caminho.endswith("/runs"):
            sha = request.url.params.get("head_sha")
            encontrados = [item for item in self.runs if item["head_sha"] == sha]
            return httpx.Response(200, json={"workflow_runs": encontrados[:1]})

        if request.method == "GET" and "/actions/runs/" in caminho:
            run_id = int(caminho.rsplit("/", 1)[1])
            for item in self.runs:
                if item["id"] == run_id:
                    corpo = dict(item)
                    if self.sha_divergente:
                        corpo["head_sha"] = "0" * 40
                    return httpx.Response(200, json=corpo)
            return httpx.Response(404, json={"message": "Not Found"})

        return httpx.Response(404, json={"message": "rota nao simulada"})


def adaptador(stub: GitHubStub, token="ghp_token_de_teste", com_probe=True):
    return GitHubExecutorAdapter(
        GitHubExecutorConfig(
            workflow="ci-repair.yml",
            api_url="https://api.github.local",
            negative_probe_ref="refs/heads/inexistente" if com_probe else None,
        ),
        token=token,
        transport=httpx.MockTransport(stub.handler),
    )


# --------------------------------------------------------------------------- #
# Bloqueios antes de qualquer chamada
# --------------------------------------------------------------------------- #


async def test_sem_token_bloqueia_antes_de_chamar_a_api():
    """O gargalo de identidade aparece cedo, não dentro do E2E."""
    stub = GitHubStub()
    resultado = await adaptador(stub, token="").executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.BLOCKED
    assert resultado.blocker == "github_token_ausente"
    assert "CENTRAL_GITHUB_TOKEN" in resultado.next_action
    assert stub.dispatches == []  # nenhuma chamada foi feita


async def test_sem_sha_bloqueia():
    resultado = await adaptador(GitHubStub()).executar(solicitacao(sha=None))
    assert resultado.outcome is ExecutionOutcome.BLOCKED
    assert resultado.blocker == "solicitacao_sem_sha"


async def test_sem_repositorio_bloqueia():
    resultado = await adaptador(GitHubStub()).executar(solicitacao(repository=None))
    assert resultado.outcome is ExecutionOutcome.BLOCKED
    assert resultado.blocker == "solicitacao_sem_repositorio"


async def test_repositorio_em_formato_invalido_bloqueia():
    resultado = await adaptador(GitHubStub()).executar(solicitacao(repository="sem-barra"))
    assert resultado.outcome is ExecutionOutcome.BLOCKED
    assert resultado.blocker == "repositorio_invalido"


async def test_repositorio_padrao_da_configuracao_e_usado():
    stub = GitHubStub()
    adapt = GitHubExecutorAdapter(
        GitHubExecutorConfig(
            workflow="ci.yml",
            api_url="https://api.github.local",
            repository="owner/padrao",
            negative_probe_ref="refs/heads/inexistente",
        ),
        token="ghp_token_de_teste",
        transport=httpx.MockTransport(stub.handler),
    )
    resultado = await adapt.executar(solicitacao(repository=None))
    assert resultado.outcome is ExecutionOutcome.SUCCESS


# --------------------------------------------------------------------------- #
# Execução e verificações
# --------------------------------------------------------------------------- #


async def test_dispara_e_comprova_as_quatro_verificacoes():
    stub = GitHubStub()
    resultado = await adaptador(stub).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.SUCCESS
    assert resultado.checks == {check: CheckResult.PASS for check in EvidenceCheck}
    assert resultado.evidence_run_url == "https://github.com/run/100"
    # Um dispatch real e um probe negativo; nenhum segundo efeito.
    assert len(stub.runs) == 1


async def test_replay_nao_dispara_de_novo():
    """Segunda execução encontra a run existente e não cria um segundo efeito."""
    stub = GitHubStub()
    await adaptador(stub).executar(solicitacao())
    dispatches_apos_primeira = len(stub.dispatches)

    resultado = await adaptador(stub).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.SUCCESS
    assert resultado.checks[EvidenceCheck.IDEMPOTENCY] is CheckResult.PASS
    assert len(stub.runs) == 1
    # Só o probe negativo foi disparado de novo; nenhum dispatch produtivo.
    assert len(stub.dispatches) == dispatches_apos_primeira + 1


async def test_sem_probe_o_controle_negativo_fica_pendente():
    stub = GitHubStub()
    resultado = await adaptador(stub, com_probe=False).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.SUCCESS
    assert EvidenceCheck.NEGATIVE_CONTROL not in resultado.checks
    assert resultado.verificacoes_pendentes == (EvidenceCheck.NEGATIVE_CONTROL,)


async def test_dispatch_recusado_vira_falha_acionavel():
    stub = GitHubStub(dispatch_recusa=True)
    resultado = await adaptador(stub).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.blocker == "github_dispatch_recusado"
    assert "actions:write" in resultado.next_action


async def test_execucao_ausente_apos_dispatch_reprova_idempotencia():
    """Dispatch aceito sem execução correspondente não comprova nada."""
    stub = GitHubStub(execucao_some=True)
    resultado = await adaptador(stub).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.checks[EvidenceCheck.IDEMPOTENCY] is CheckResult.FAIL
    assert resultado.blocker == "github_execucao_nao_encontrada"


async def test_leitura_independente_divergente_reprova():
    stub = GitHubStub(sha_divergente=True)
    resultado = await adaptador(stub).executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.checks[EvidenceCheck.INDEPENDENT_READ] is CheckResult.FAIL


async def test_api_indisponivel_vira_falha_acionavel():
    async def indisponivel(_request):
        raise httpx.ConnectError("conexão recusada")

    adapt = GitHubExecutorAdapter(
        GitHubExecutorConfig(workflow="ci.yml", api_url="https://api.github.local"),
        token="ghp_token_de_teste",
        transport=httpx.MockTransport(indisponivel),
    )
    resultado = await adapt.executar(solicitacao())

    assert resultado.outcome is ExecutionOutcome.FAILED
    assert resultado.blocker == "github_api_indisponivel"


async def test_token_nunca_aparece_no_detalhe_da_falha():
    async def erro_com_token(_request):
        raise httpx.ConnectError("falha usando Bearer ghp_abcdefghijklmnopqrstuvwxyz0123456789")

    adapt = GitHubExecutorAdapter(
        GitHubExecutorConfig(workflow="ci.yml", api_url="https://api.github.local"),
        token="ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        transport=httpx.MockTransport(erro_com_token),
    )
    resultado = await adapt.executar(solicitacao())

    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in (resultado.detail or "")
    assert "[REDACTED]" in (resultado.detail or "")


async def test_inputs_do_dispatch_rastreiam_a_solicitacao():
    stub = GitHubStub()
    await adaptador(stub).executar(solicitacao())

    produtivo = stub.dispatches[0]
    assert produtivo["ref"] == "main"
    assert produtivo["inputs"]["request_id"] == "WR-1"
    assert produtivo["inputs"]["correlation_id"] == "corr-12345678"
    assert produtivo["inputs"]["sha"] == SHA
    assert len(produtivo["inputs"]["idempotency_key"]) == 64


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #


def test_registry_constroi_executor_github():
    registry = registry_de_configuracao(
        json.dumps({"ci_repair": {"kind": "github", "workflow": "ci-repair.yml"}}),
        github_token="ghp_token",
    )
    assert isinstance(registry.para(ExecutorKind.CI_REPAIR), GitHubExecutorAdapter)


def test_registry_recusa_github_sem_workflow():
    with pytest.raises(ValueError, match="exige 'workflow'"):
        registry_de_configuracao(json.dumps({"ci_repair": {"kind": "github"}}))


def test_registry_recusa_campo_github_com_tipo_errado():
    with pytest.raises(ValueError, match="deve ser texto"):
        registry_de_configuracao(
            json.dumps({"ci_repair": {"kind": "github", "workflow": "ci.yml", "repository": 42}})
        )


def test_registry_mantem_http_quando_kind_nao_e_github():
    from app.infrastructure.executors.http_executor import HttpExecutorAdapter

    registry = registry_de_configuracao(json.dumps({"graph": "https://executor/graph"}))
    assert isinstance(registry.para(ExecutorKind.GRAPH), HttpExecutorAdapter)
