"""Serviço da Central: fila -> roteador -> WIP -> execução -> evidência.

Fecha o ciclo operacional em um único ponto de estado:

* toda solicitação entra classificada (executor decidido pela Central);
* a admissão respeita o limite de causas raiz ativas;
* ``proximo_item`` devolve deterministicamente o próximo trabalho executável;
* a conclusão só é aceita com evidência ``EVIDENCED`` no SHA corrente.

O estado vive em um ``CentralStore``: em memória para DEV e testes, em Redis
para operação real. O serviço não guarda estado próprio, de modo que várias
réplicas da API compartilhem a mesma fila e o mesmo ledger.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.domain.central.evidence_ledger import (
    EvidenceRecord,
    EvidenceRecordInput,
    EvidenceStatus,
)
from app.domain.central.executor_router import ExecutorRouter
from app.domain.central.metrics import CentralMetrics, calcular_metricas
from app.domain.central.models import (
    ACTIVE_STATUSES,
    ExecutorKind,
    WorkRequest,
    WorkRequestInput,
    WorkRequestStatus,
    agora,
)
from app.domain.central.wip_policy import AdmissionPlan, WipPolicy
from app.infrastructure.repositories.central_store import CentralStore, InMemoryCentralStore


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
        store: CentralStore | None = None,
    ) -> None:
        self._router = router or ExecutorRouter()
        self._wip = wip_policy or WipPolicy()
        self._store: CentralStore = store or InMemoryCentralStore()

    @property
    def store(self) -> CentralStore:
        return self._store

    @property
    def wip_policy(self) -> WipPolicy:
        return self._wip

    async def registrar(self, entrada: WorkRequestInput) -> WorkRequest:
        """Registra de forma idempotente por (correlation_id, projeto, título).

        A criação é atômica no store: um replay do produtor devolve a mesma
        solicitação em vez de criar uma segunda com outro id.
        """
        decisao = self._router.route(entrada)
        momento = agora()
        solicitacao = WorkRequest(
            request_id=self._gerar_request_id(entrada),
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
        armazenada, _ = await self._store.criar_se_ausente(solicitacao)
        return armazenada

    async def obter(self, request_id: str) -> WorkRequest:
        solicitacao = await self._store.obter(request_id)
        if solicitacao is None:
            raise WorkRequestNotFoundError(request_id)
        return solicitacao

    async def listar(self) -> tuple[WorkRequest, ...]:
        return tuple(await self._store.listar())

    async def plano_de_admissao(self) -> AdmissionPlan:
        return self._wip.plan(await self._store.listar())

    async def aplicar_admissao(self) -> CentralSnapshot:
        """Aplica o plano de WIP: admite as causas com vaga, enfileira o resto.

        É idempotente e recalculada a partir do estado persistido, de modo que
        rodar em duas réplicas converge para a mesma decisão.
        """
        plano = self._wip.plan(await self._store.listar())
        admitidas = set(plano.admitted_request_ids)
        enfileiradas = set(plano.queued_request_ids)

        for request_id in sorted(admitidas):
            await self._store.atualizar(
                request_id,
                lambda item: self._promover(item, WorkRequestStatus.ADMITTED),
            )
        for request_id in sorted(enfileiradas):
            await self._store.atualizar(
                request_id,
                lambda item: self._promover(item, WorkRequestStatus.QUEUED),
            )

        return CentralSnapshot(requests=tuple(await self._store.listar()), plan=plano)

    async def proximo_item(self, executor: ExecutorKind | None = None) -> WorkRequest | None:
        """Próximo trabalho executável, já admitido e com executor automático."""
        snapshot = await self.aplicar_admissao()
        candidatos = [
            item
            for item in snapshot.requests
            if item.status == WorkRequestStatus.ADMITTED
            and item.executor is not ExecutorKind.HUMAN_GATE
            and (executor is None or item.executor is executor)
        ]
        if not candidatos:
            return None
        ordem = {request_id: indice for indice, request_id in enumerate(snapshot.plan.admitted_request_ids)}
        candidatos.sort(key=lambda item: (ordem.get(item.request_id, len(ordem)), item.request_id))
        return candidatos[0]

    async def transicionar(
        self,
        request_id: str,
        novo_status: WorkRequestStatus,
        blocker: str | None = None,
        next_action: str | None = None,
    ) -> WorkRequest:
        if novo_status == WorkRequestStatus.EVIDENCED:
            # Lido antes do CAS: a evidência é o gate, e o store só grava se a
            # solicitação ainda estiver no estado que o mutator aceita.
            solicitacao = await self.obter(request_id)
            status_evidencia = await self._store.status_evidencia(request_id, solicitacao.sha)
            if status_evidencia is not EvidenceStatus.EVIDENCED:
                raise InvalidTransitionError(
                    f"conclusão exige evidência EVIDENCED no SHA corrente (atual: {status_evidencia.value})"
                )

        def mutator(atual: WorkRequest) -> WorkRequest:
            if novo_status not in _TRANSICOES[atual.status]:
                raise InvalidTransitionError(
                    f"transição {atual.status.value} -> {novo_status.value} não permitida"
                )
            atualizacao: dict[str, object] = {"status": novo_status, "updated_at": agora()}
            if novo_status == WorkRequestStatus.BLOCKED:
                if not (blocker and next_action):
                    raise InvalidTransitionError("bloqueio exige blocker e next_action")
                atualizacao.update({"blocker": blocker, "next_action": next_action})
            else:
                atualizacao.update({"blocker": None, "next_action": next_action})
            return atual.model_copy(update=atualizacao)

        atualizada = await self._store.atualizar(request_id, mutator)
        if atualizada is None:
            raise WorkRequestNotFoundError(request_id)
        return atualizada

    async def registrar_evidencia(self, entrada: EvidenceRecordInput) -> EvidenceRecord:
        """Grava a evidência e alinha o estado da solicitação.

        A evidência é gravada primeiro porque é a fonte da verdade da conclusão:
        se o processo cair antes de alinhar a solicitação, o status dela fica
        atrasado, mas ``transicionar`` continua consultando o ledger e nenhuma
        conclusão indevida passa.
        """
        if await self._store.obter(entrada.request_id) is None:
            raise WorkRequestNotFoundError(entrada.request_id)

        registro = await self._store.registrar_evidencia(entrada)

        def mutator(atual: WorkRequest) -> WorkRequest:
            atualizacao: dict[str, object] = {"sha": entrada.sha, "updated_at": agora()}
            if atual.status in ACTIVE_STATUSES and registro.status is not EvidenceStatus.BLOCKED:
                atualizacao["status"] = WorkRequestStatus.AWAITING_EVIDENCE
            return atual.model_copy(update=atualizacao)

        await self._store.atualizar(entrada.request_id, mutator)
        return registro

    async def metricas(self) -> CentralMetrics:
        """Fotografia operacional da Central a partir do estado persistido.

        A evidência é lida por solicitação (N+1). No volume da Central isso é
        irrelevante e mantém o store livre de uma consulta especializada; se um
        dia doer, o lugar de otimizar é o store, não este cálculo.
        """
        solicitacoes = await self._store.listar()
        evidencias: dict[str, EvidenceRecord] = {}
        for solicitacao in solicitacoes:
            registro = await self._store.obter_evidencia(solicitacao.request_id)
            if registro is not None:
                evidencias[solicitacao.request_id] = registro
        return calcular_metricas(solicitacoes, evidencias, self._wip.plan(solicitacoes))

    async def obter_evidencia(self, request_id: str) -> EvidenceRecord | None:
        return await self._store.obter_evidencia(request_id)

    async def historico_evidencia(self, request_id: str) -> tuple[EvidenceRecord, ...]:
        return await self._store.historico_evidencia(request_id)

    @staticmethod
    def _promover(atual: WorkRequest, destino: WorkRequestStatus) -> WorkRequest:
        """Aplica a decisão de WIP sem tocar em trabalho já iniciado."""
        if destino == WorkRequestStatus.ADMITTED and atual.status in {
            WorkRequestStatus.RECEIVED,
            WorkRequestStatus.QUEUED,
        }:
            return atual.model_copy(update={"status": destino, "updated_at": agora()})
        if destino == WorkRequestStatus.QUEUED and atual.status == WorkRequestStatus.RECEIVED:
            return atual.model_copy(update={"status": destino, "updated_at": agora()})
        return atual

    @staticmethod
    def _gerar_request_id(entrada: WorkRequestInput) -> str:
        semente = "|".join((entrada.correlation_id, entrada.project, entrada.title))
        digest = hashlib.sha256(semente.encode("utf-8")).hexdigest()[:24].upper()
        return f"WR-{digest}"
