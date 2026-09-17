"""Serviço da Central: fila -> roteador -> WIP -> execução -> evidência.

Fecha o ciclo operacional em um único ponto de estado:

* toda solicitação entra classificada (executor decidido pela Central);
* a admissão respeita o limite de causas raiz ativas;
* ``proximo_item`` devolve deterministicamente o próximo trabalho executável;
* a conclusão só é aceita com evidência ``EVIDENCED`` no SHA corrente.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass

from app.domain.central.evidence_ledger import (
    EvidenceLedger,
    EvidenceRecord,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.executor_router import ExecutorRouter
from app.domain.central.models import (
    ACTIVE_STATUSES,
    ExecutorKind,
    WorkRequest,
    WorkRequestInput,
    WorkRequestStatus,
    agora,
)
from app.domain.central.wip_policy import AdmissionPlan, WipPolicy


class WorkRequestNotFoundError(LookupError):
    """A solicitação informada não existe na Central."""


class InvalidTransitionError(ValueError):
    """Transição de estado recusada pelo ciclo operacional."""


@dataclass(frozen=True)
class CentralSnapshot:
    requests: tuple[WorkRequest, ...]
    plan: AdmissionPlan


#: Transições permitidas no ciclo operacional.
_TRANSICOES: dict[WorkRequestStatus, frozenset[WorkRequestStatus]] = {
    WorkRequestStatus.RECEIVED: frozenset({WorkRequestStatus.QUEUED, WorkRequestStatus.ADMITTED, WorkRequestStatus.BLOCKED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.QUEUED: frozenset({WorkRequestStatus.ADMITTED, WorkRequestStatus.BLOCKED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.ADMITTED: frozenset({WorkRequestStatus.EXECUTING, WorkRequestStatus.QUEUED, WorkRequestStatus.BLOCKED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.EXECUTING: frozenset({WorkRequestStatus.AWAITING_EVIDENCE, WorkRequestStatus.BLOCKED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.AWAITING_EVIDENCE: frozenset({WorkRequestStatus.EVIDENCED, WorkRequestStatus.EXECUTING, WorkRequestStatus.BLOCKED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.BLOCKED: frozenset({WorkRequestStatus.QUEUED, WorkRequestStatus.ADMITTED, WorkRequestStatus.CANCELLED}),
    WorkRequestStatus.EVIDENCED: frozenset(),
    WorkRequestStatus.CANCELLED: frozenset(),
}


class CentralService:
    def __init__(
        self,
        router: ExecutorRouter | None = None,
        wip_policy: WipPolicy | None = None,
        ledger: EvidenceLedger | None = None,
    ) -> None:
        self._router = router or ExecutorRouter()
        self._wip = wip_policy or WipPolicy()
        self._ledger = ledger or EvidenceLedger()
        self._requests: dict[str, WorkRequest] = {}
        self._lock = asyncio.Lock()

    @property
    def ledger(self) -> EvidenceLedger:
        return self._ledger

    @property
    def wip_policy(self) -> WipPolicy:
        return self._wip

    async def registrar(self, entrada: WorkRequestInput) -> WorkRequest:
        """Registra de forma idempotente por (correlation_id, título, projeto)."""
        request_id = self._gerar_request_id(entrada)
        async with self._lock:
            existente = self._requests.get(request_id)
            if existente is not None:
                return existente.model_copy(deep=True)

            decisao = self._router.route(entrada)
            momento = agora()
            solicitacao = WorkRequest(
                request_id=request_id,
                title=entrada.title,
                project=entrada.project,
                environment=entrada.environment,
                priority=entrada.priority,
                root_cause_id=entrada.root_cause_id,
                correlation_id=entrada.correlation_id,
                signals=entrada.signals,
                target_system=entrada.target_system,
                repository=entrada.repository,
                branch=entrada.branch,
                sha=entrada.sha,
                completion_criteria=entrada.completion_criteria,
                origin_url=entrada.origin_url,
                executor=decisao.executor,
                routing_rule=decisao.rule_id,
                status=WorkRequestStatus.BLOCKED if decisao.requires_human else WorkRequestStatus.RECEIVED,
                blocker=decisao.human_reason if decisao.requires_human else None,
                next_action=(
                    "Resolver dependência humana antes de admitir na fila executável."
                    if decisao.requires_human
                    else None
                ),
                created_at=momento,
                updated_at=momento,
            )
            self._requests[request_id] = solicitacao
            return solicitacao.model_copy(deep=True)

    async def obter(self, request_id: str) -> WorkRequest:
        solicitacao = self._requests.get(request_id)
        if solicitacao is None:
            raise WorkRequestNotFoundError(request_id)
        return solicitacao.model_copy(deep=True)

    async def listar(self) -> tuple[WorkRequest, ...]:
        return tuple(item.model_copy(deep=True) for item in self._requests.values())

    async def plano_de_admissao(self) -> AdmissionPlan:
        return self._wip.plan(list(self._requests.values()))

    async def aplicar_admissao(self) -> CentralSnapshot:
        """Aplica o plano de WIP: admite as causas com vaga, enfileira o resto."""
        async with self._lock:
            plano = self._wip.plan(list(self._requests.values()))
            admitidas = set(plano.admitted_request_ids)
            enfileiradas = set(plano.queued_request_ids)
            momento = agora()

            for request_id in admitidas:
                solicitacao = self._requests[request_id]
                if solicitacao.status in {WorkRequestStatus.RECEIVED, WorkRequestStatus.QUEUED}:
                    self._requests[request_id] = solicitacao.model_copy(
                        update={"status": WorkRequestStatus.ADMITTED, "updated_at": momento}
                    )

            for request_id in enfileiradas:
                solicitacao = self._requests[request_id]
                if solicitacao.status == WorkRequestStatus.RECEIVED:
                    self._requests[request_id] = solicitacao.model_copy(
                        update={"status": WorkRequestStatus.QUEUED, "updated_at": momento}
                    )

            return CentralSnapshot(
                requests=tuple(item.model_copy(deep=True) for item in self._requests.values()),
                plan=plano,
            )

    async def proximo_item(self, executor: ExecutorKind | None = None) -> WorkRequest | None:
        """Próximo trabalho executável, já admitido e com executor automático."""
        await self.aplicar_admissao()
        candidatos = [
            item
            for item in self._requests.values()
            if item.status == WorkRequestStatus.ADMITTED
            and item.executor is not ExecutorKind.HUMAN_GATE
            and (executor is None or item.executor is executor)
        ]
        if not candidatos:
            return None
        plano = self._wip.plan(list(self._requests.values()))
        ordem = {request_id: indice for indice, request_id in enumerate(plano.admitted_request_ids)}
        candidatos.sort(key=lambda item: ordem.get(item.request_id, len(ordem)))
        return candidatos[0].model_copy(deep=True)

    async def transicionar(
        self,
        request_id: str,
        novo_status: WorkRequestStatus,
        blocker: str | None = None,
        next_action: str | None = None,
    ) -> WorkRequest:
        async with self._lock:
            solicitacao = self._requests.get(request_id)
            if solicitacao is None:
                raise WorkRequestNotFoundError(request_id)
            if novo_status not in _TRANSICOES[solicitacao.status]:
                raise InvalidTransitionError(
                    f"transição {solicitacao.status.value} -> {novo_status.value} não permitida"
                )
            if novo_status == WorkRequestStatus.EVIDENCED:
                status_evidencia = self._ledger.status_para(request_id, solicitacao.sha)
                if status_evidencia is not EvidenceStatus.EVIDENCED:
                    raise InvalidTransitionError(
                        f"conclusão exige evidência EVIDENCED no SHA corrente (atual: {status_evidencia.value})"
                    )

            atualizacao: dict[str, object] = {"status": novo_status, "updated_at": agora()}
            if novo_status == WorkRequestStatus.BLOCKED:
                if not (blocker and next_action):
                    raise InvalidTransitionError("bloqueio exige blocker e next_action")
                atualizacao.update({"blocker": blocker, "next_action": next_action})
            else:
                atualizacao.update({"blocker": None, "next_action": next_action})

            atualizada = solicitacao.model_copy(update=atualizacao)
            self._requests[request_id] = atualizada
            return atualizada.model_copy(deep=True)

    async def registrar_evidencia(self, entrada: EvidenceRecordInput) -> EvidenceRecord:
        async with self._lock:
            solicitacao = self._requests.get(entrada.request_id)
            if solicitacao is None:
                raise WorkRequestNotFoundError(entrada.request_id)
            registro = self._ledger.registrar(entrada)
            atualizacao: dict[str, object] = {"sha": entrada.sha, "updated_at": agora()}
            if solicitacao.status in ACTIVE_STATUSES and registro.status is not EvidenceStatus.BLOCKED:
                atualizacao["status"] = WorkRequestStatus.AWAITING_EVIDENCE
            self._requests[entrada.request_id] = solicitacao.model_copy(update=atualizacao)
            return registro

    @staticmethod
    def _gerar_request_id(entrada: WorkRequestInput) -> str:
        semente = "|".join((entrada.correlation_id, entrada.project, entrada.title))
        digest = hashlib.sha256(semente.encode("utf-8")).hexdigest()[:24].upper()
        return f"WR-{digest}"
