"""Executor nativo de GitHub Actions: dispara um workflow e comprova o efeito.

Efeito produzido: um ``workflow_dispatch`` no repositório e SHA da solicitação,
carregando `request_id`, `correlation_id` e `idempotency_key` como inputs — de
modo que a execução resultante seja rastreável até a Solicitação de Trabalho.

Como cada verificação é comprovada:

* **positivo** — o dispatch é aceito (204) e uma execução aparece para o SHA;
* **idempotência** — antes de disparar, o adaptador procura uma execução já
  existente para (workflow, SHA, `workflow_dispatch`). Se existe, **não
  dispara** e reporta o efeito existente. Na primeira execução, ele reexecuta
  essa mesma decisão depois do dispatch e confirma que um replay agora
  resolveria para a execução existente — verifica o mecanismo sem produzir um
  segundo efeito, que é justamente o que não se pode fazer no GitHub;
* **leitura independente** — a execução é relida pelo endpoint de runs, não
  pela resposta do dispatch (que não devolve corpo algum);
* **controle negativo** — quando habilitado, dispara para uma ref inexistente e
  exige recusa 4xx. Sem isso a verificação fica ``PENDING`` e a solicitação não
  é concluída.

Sem token, o adaptador **bloqueia** com causa explícita em vez de tentar e
falhar na autenticação dentro do E2E. É o gargalo de identidade aparecendo cedo,
onde custa barato.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.central.evidence_ledger import CheckResult, EvidenceCheck
from app.domain.central.execution import ExecutionOutcome, ExecutionResult
from app.domain.central.models import WorkRequest

REPOSITORIO_VALIDO = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class GitHubExecutorConfig:
    #: Arquivo do workflow a disparar, por exemplo ``ci-repair.yml``.
    workflow: str
    api_url: str = "https://api.github.com"
    #: Repositório padrão quando a solicitação não informa um.
    repository: str | None = None
    #: Ref inexistente usada como controle negativo; ``None`` desliga a verificação.
    negative_probe_ref: str | None = None


class GitHubExecutorAdapter:
    def __init__(
        self,
        config: GitHubExecutorConfig,
        token: str = "",
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._token = token.strip()
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._transport = transport

    async def executar(self, solicitacao: WorkRequest) -> ExecutionResult:
        bloqueio = self._pre_condicoes(solicitacao)
        if bloqueio is not None:
            return bloqueio

        repositorio = solicitacao.repository or self._config.repository
        ref = solicitacao.branch or solicitacao.sha
        chave = _idempotency_key(solicitacao)
        checks: dict[EvidenceCheck, CheckResult] = {}

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                existente = await self._execucao_existente(client, repositorio, solicitacao.sha)
            except httpx.HTTPError as exc:
                return self._falha("github_api_indisponivel", exc)

            if existente is not None:
                # Replay: a execução já existe, então não se dispara de novo.
                checks[EvidenceCheck.POSITIVE] = CheckResult.PASS
                checks[EvidenceCheck.IDEMPOTENCY] = CheckResult.PASS
                execucao = existente
            else:
                try:
                    aceito = await self._disparar(client, repositorio, ref, solicitacao, chave)
                except httpx.HTTPError as exc:
                    return self._falha("github_dispatch_falhou", exc)
                if not aceito:
                    return ExecutionResult(
                        outcome=ExecutionOutcome.FAILED,
                        blocker="github_dispatch_recusado",
                        next_action=(
                            "Verificar se o workflow existe, aceita workflow_dispatch e se a "
                            "identidade tem permissão de actions:write no repositório."
                        ),
                    )
                checks[EvidenceCheck.POSITIVE] = CheckResult.PASS

                try:
                    execucao = await self._execucao_existente(client, repositorio, solicitacao.sha)
                except httpx.HTTPError:
                    execucao = None
                # A idempotência é verificada pelo mecanismo, não por um segundo
                # dispatch: se o guard agora encontra a execução, um replay não
                # criaria um segundo efeito.
                checks[EvidenceCheck.IDEMPOTENCY] = (
                    CheckResult.PASS if execucao is not None else CheckResult.FAIL
                )

            if execucao is None:
                return ExecutionResult(
                    outcome=ExecutionOutcome.FAILED,
                    checks=checks,
                    blocker="github_execucao_nao_encontrada",
                    next_action=(
                        "O dispatch foi aceito mas nenhuma execução apareceu para o SHA; "
                        "verificar filtros de branch e gatilhos do workflow."
                    ),
                )

            # Leitura independente: relê a execução pelo id, não pelo filtro.
            try:
                lida = await self._ler_execucao(client, repositorio, execucao["id"])
                checks[EvidenceCheck.INDEPENDENT_READ] = (
                    CheckResult.PASS
                    if str(lida.get("head_sha")) == solicitacao.sha
                    else CheckResult.FAIL
                )
            except httpx.HTTPError:
                checks[EvidenceCheck.INDEPENDENT_READ] = CheckResult.PENDING

            if self._config.negative_probe_ref:
                checks[EvidenceCheck.NEGATIVE_CONTROL] = await self._controle_negativo(
                    client, repositorio, solicitacao, chave
                )

        if any(resultado is CheckResult.FAIL for resultado in checks.values()):
            reprovadas = sorted(
                check.value for check, resultado in checks.items() if resultado is CheckResult.FAIL
            )
            return ExecutionResult(
                outcome=ExecutionOutcome.FAILED,
                checks=checks,
                evidence_run_url=execucao.get("html_url"),
                blocker=f"verificacoes_reprovadas:{','.join(reprovadas)}",
                next_action="Investigar o workflow: a execução não sustenta as verificações.",
            )

        return ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            checks=checks,
            evidence_run_url=execucao.get("html_url"),
            detail=f"run_id={execucao['id']}",
        )

    def _pre_condicoes(self, solicitacao: WorkRequest) -> ExecutionResult | None:
        """Falta de identidade ou de alvo bloqueia antes de qualquer chamada."""
        if not self._token:
            return ExecutionResult(
                outcome=ExecutionOutcome.BLOCKED,
                blocker="github_token_ausente",
                next_action=(
                    "Provisionar CENTRAL_GITHUB_TOKEN com escopo actions:write no cofre "
                    "e reiniciar o runtime. Depende de autorização humana."
                ),
            )
        if not solicitacao.sha:
            return ExecutionResult(
                outcome=ExecutionOutcome.BLOCKED,
                blocker="solicitacao_sem_sha",
                next_action="Informar o SHA: evidência sem SHA não comprova versão alguma.",
            )
        repositorio = solicitacao.repository or self._config.repository
        if not repositorio:
            return ExecutionResult(
                outcome=ExecutionOutcome.BLOCKED,
                blocker="solicitacao_sem_repositorio",
                next_action=(
                    "Informar 'repository' na solicitação ou configurar um repositório padrão."
                ),
            )
        if not REPOSITORIO_VALIDO.match(repositorio):
            return ExecutionResult(
                outcome=ExecutionOutcome.BLOCKED,
                blocker="repositorio_invalido",
                next_action=f"Usar o formato owner/repo; recebido '{repositorio[:100]}'.",
            )
        return None

    async def _execucao_existente(
        self, client: httpx.AsyncClient, repositorio: str, sha: str
    ) -> dict[str, Any] | None:
        url = (
            f"{self._config.api_url}/repos/{repositorio}/actions/workflows/"
            f"{self._config.workflow}/runs"
        )
        resposta = await client.get(
            url,
            params={"event": "workflow_dispatch", "head_sha": sha, "per_page": 1},
            headers=self._headers(),
        )
        resposta.raise_for_status()
        execucoes = (resposta.json() or {}).get("workflow_runs") or []
        return execucoes[0] if execucoes else None

    async def _disparar(
        self,
        client: httpx.AsyncClient,
        repositorio: str,
        ref: str | None,
        solicitacao: WorkRequest,
        chave: str,
    ) -> bool:
        url = (
            f"{self._config.api_url}/repos/{repositorio}/actions/workflows/"
            f"{self._config.workflow}/dispatches"
        )
        resposta = await client.post(
            url,
            json={
                "ref": ref,
                "inputs": {
                    "request_id": solicitacao.request_id,
                    "correlation_id": solicitacao.correlation_id,
                    "idempotency_key": chave,
                    "sha": solicitacao.sha,
                },
            },
            headers=self._headers(),
        )
        if resposta.status_code >= 500:
            resposta.raise_for_status()
        return resposta.status_code == 204

    async def _ler_execucao(
        self, client: httpx.AsyncClient, repositorio: str, run_id: Any
    ) -> dict[str, Any]:
        resposta = await client.get(
            f"{self._config.api_url}/repos/{repositorio}/actions/runs/{run_id}",
            headers=self._headers(),
        )
        resposta.raise_for_status()
        return resposta.json() or {}

    async def _controle_negativo(
        self,
        client: httpx.AsyncClient,
        repositorio: str,
        solicitacao: WorkRequest,
        chave: str,
    ) -> CheckResult:
        """O GitHub precisa **recusar** um dispatch para ref inexistente."""
        try:
            aceito = await self._disparar(
                client, repositorio, self._config.negative_probe_ref, solicitacao, chave
            )
        except httpx.HTTPError:
            return CheckResult.PENDING
        # Aceitar uma ref inexistente significaria que o alvo não é validado.
        return CheckResult.FAIL if aceito else CheckResult.PASS

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self._token}",
        }

    @staticmethod
    def _falha(blocker: str, exc: Exception) -> ExecutionResult:
        return ExecutionResult(
            outcome=ExecutionOutcome.FAILED,
            blocker=blocker,
            next_action="Verificar disponibilidade da API do GitHub e a validade do token.",
            detail=_sanitizar(str(exc)),
        )


def _idempotency_key(solicitacao: WorkRequest) -> str:
    semente = f"{solicitacao.request_id}|{solicitacao.sha}"
    return hashlib.sha256(semente.encode("utf-8")).hexdigest()


def _sanitizar(mensagem: str) -> str:
    limpa = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", mensagem)
    limpa = re.sub(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,})", "[REDACTED]", limpa)
    limpa = re.sub(r"(?i)(token|secret|password|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", limpa)
    return limpa[:500]
