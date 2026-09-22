"""Executor HTTP: produz o efeito chamando o endpoint do executor concreto.

Contrato esperado do endpoint (mesmo para CI, Graph, SQL ou Drive — o que muda
é quem está do outro lado):

``POST {url}`` com o corpo da solicitação e ``idempotency_key``; resposta::

    {"accepted": true,
     "effect_id": "<id do efeito>",
     "duplicate_effect": false,
     "verification_url": "<URL de leitura independente>",
     "evidence_run_url": "<opcional: execução que comprova>"}

O adaptador então:

1. **caso positivo** — o POST foi aceito e devolveu ``effect_id``;
2. **idempotência** — repete o POST com a mesma ``idempotency_key`` e exige
   ``duplicate_effect: true`` com o mesmo ``effect_id``; efeito duplicado
   reprova;
3. **leitura independente** — ``GET verification_url`` precisa confirmar o
   mesmo ``effect_id``;
4. **controle negativo** — só quando o endpoint declara um ``negative_probe``
   na configuração: envia a carga inválida e exige recusa 4xx.

Verificação que o endpoint não suporta **não vira PASS**: fica ``PENDING``, a
evidência permanece ``PARTIAL`` e a solicitação não é concluída. É por isso que
um executor não consegue, sozinho, declarar trabalho comprovado.
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


@dataclass(frozen=True)
class HttpExecutorEndpoint:
    url: str
    #: Carga deliberadamente inválida; o endpoint precisa recusá-la com 4xx.
    negative_probe: dict[str, Any] | None = None
    service_token_env: str | None = None


class HttpExecutorAdapter:
    def __init__(
        self,
        endpoint: HttpExecutorEndpoint,
        timeout_seconds: float = 20.0,
        service_token: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._service_token = service_token.strip()
        self._transport = transport

    async def executar(self, solicitacao: WorkRequest) -> ExecutionResult:
        if not solicitacao.sha:
            return ExecutionResult(
                outcome=ExecutionOutcome.BLOCKED,
                blocker="solicitacao_sem_sha",
                next_action=(
                    "Informar o SHA da solicitação: evidência sem SHA não comprova versão alguma."
                ),
            )

        payload = self._payload(solicitacao)
        checks: dict[EvidenceCheck, CheckResult] = {}

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                primeira = await self._postar(client, payload, solicitacao.correlation_id)
            except httpx.HTTPError as exc:
                return self._falha("executor_http_indisponivel", exc)

            if not primeira.get("accepted") or not primeira.get("effect_id"):
                return ExecutionResult(
                    outcome=ExecutionOutcome.FAILED,
                    blocker="executor_recusou_solicitacao",
                    next_action="Inspecionar o executor: resposta sem accepted/effect_id.",
                    detail=_sanitizar(str(primeira)[:400]),
                )

            effect_id = str(primeira["effect_id"])
            checks[EvidenceCheck.POSITIVE] = CheckResult.PASS
            evidence_run_url = primeira.get("evidence_run_url")

            # 2. Idempotência: o replay não pode criar um segundo efeito.
            try:
                segunda = await self._postar(client, payload, solicitacao.correlation_id)
                mesmo_efeito = str(segunda.get("effect_id")) == effect_id
                checks[EvidenceCheck.IDEMPOTENCY] = (
                    CheckResult.PASS
                    if segunda.get("duplicate_effect") and mesmo_efeito
                    else CheckResult.FAIL
                )
            except httpx.HTTPError:
                checks[EvidenceCheck.IDEMPOTENCY] = CheckResult.PENDING

            # 3. Leitura independente: outra fonte precisa confirmar o efeito.
            verification_url = primeira.get("verification_url")
            if verification_url:
                try:
                    lido = await self._ler(client, str(verification_url), solicitacao.correlation_id)
                    checks[EvidenceCheck.INDEPENDENT_READ] = (
                        CheckResult.PASS if str(lido.get("effect_id")) == effect_id else CheckResult.FAIL
                    )
                except httpx.HTTPError:
                    checks[EvidenceCheck.INDEPENDENT_READ] = CheckResult.PENDING

            # 4. Controle negativo: só quando o executor declara suportá-lo.
            if self._endpoint.negative_probe is not None:
                checks[EvidenceCheck.NEGATIVE_CONTROL] = await self._controle_negativo(
                    client, solicitacao.correlation_id
                )

        if any(resultado is CheckResult.FAIL for resultado in checks.values()):
            reprovadas = sorted(
                check.value for check, resultado in checks.items() if resultado is CheckResult.FAIL
            )
            return ExecutionResult(
                outcome=ExecutionOutcome.FAILED,
                checks=checks,
                evidence_run_url=evidence_run_url,
                blocker=f"verificacoes_reprovadas:{','.join(reprovadas)}",
                next_action="Corrigir o executor: o efeito não sustenta as verificações exigidas.",
            )

        return ExecutionResult(
            outcome=ExecutionOutcome.SUCCESS,
            checks=checks,
            evidence_run_url=evidence_run_url,
            detail=f"effect_id={effect_id}",
        )

    async def _controle_negativo(self, client: httpx.AsyncClient, correlation_id: str) -> CheckResult:
        """O executor precisa **recusar** uma carga inválida, não aceitá-la."""
        try:
            resposta = await client.post(
                self._endpoint.url,
                json=self._endpoint.negative_probe,
                headers=self._headers(correlation_id),
            )
        except httpx.HTTPError:
            return CheckResult.PENDING
        return CheckResult.PASS if 400 <= resposta.status_code < 500 else CheckResult.FAIL

    async def _postar(
        self, client: httpx.AsyncClient, payload: dict[str, Any], correlation_id: str
    ) -> dict[str, Any]:
        resposta = await client.post(
            self._endpoint.url, json=payload, headers=self._headers(correlation_id)
        )
        resposta.raise_for_status()
        return resposta.json() if resposta.content else {}

    async def _ler(
        self, client: httpx.AsyncClient, url: str, correlation_id: str
    ) -> dict[str, Any]:
        resposta = await client.get(url, headers=self._headers(correlation_id))
        resposta.raise_for_status()
        return resposta.json() if resposta.content else {}

    def _headers(self, correlation_id: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "X-Correlation-Id": correlation_id}
        if self._service_token:
            headers["X-Service-Token"] = self._service_token
        return headers

    @staticmethod
    def _payload(solicitacao: WorkRequest) -> dict[str, Any]:
        return {
            "request_id": solicitacao.request_id,
            "correlation_id": solicitacao.correlation_id,
            "idempotency_key": _idempotency_key(solicitacao),
            "executor": solicitacao.executor.value,
            "project": solicitacao.project,
            "environment": solicitacao.environment.value,
            "repository": solicitacao.repository,
            "branch": solicitacao.branch,
            "sha": solicitacao.sha,
            "title": solicitacao.title,
            "signals": list(solicitacao.signals),
        }

    @staticmethod
    def _falha(blocker: str, exc: Exception) -> ExecutionResult:
        return ExecutionResult(
            outcome=ExecutionOutcome.FAILED,
            blocker=blocker,
            next_action="Verificar disponibilidade e configuração do endpoint do executor.",
            detail=_sanitizar(str(exc)),
        )


def _idempotency_key(solicitacao: WorkRequest) -> str:
    """Mesma solicitação no mesmo SHA produz a mesma chave — e um só efeito."""
    semente = f"{solicitacao.request_id}|{solicitacao.sha}"
    return hashlib.sha256(semente.encode("utf-8")).hexdigest()


def _sanitizar(mensagem: str) -> str:
    limpa = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", mensagem)
    limpa = re.sub(r"(?i)(token|secret|password|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", limpa)
    return limpa[:500]
