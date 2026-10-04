"""WIP limitado por causa raiz, não por solicitação.

Vinte sintomas frequentemente são três defeitos. Admitir trabalho por sintoma
multiplica frentes simultâneas sem aumentar a vazão de trabalho concluído. A
política abaixo limita quantas *causas raiz* podem estar ativas ao mesmo tempo;
solicitações de causas não admitidas permanecem em fila determinística.

Ordenação de admissão (determinística, sem desempate arbitrário):
1. maior prioridade da causa raiz (P0 antes de P1...);
2. causa com solicitação mais antiga primeiro;
3. ``root_cause_id`` em ordem alfabética.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.central.models import (
    ACTIVE_STATUSES,
    Priority,
    WorkRequest,
    WorkRequestStatus,
)

DEFAULT_MAX_ACTIVE_ROOT_CAUSES = 3

_PRIORITY_ORDER = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2, Priority.P3: 3}


@dataclass(frozen=True)
class RootCauseSlot:
    root_cause_id: str
    priority: Priority
    oldest_created_at: datetime
    request_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionPlan:
    max_active_root_causes: int
    admitted: tuple[RootCauseSlot, ...]
    queued: tuple[RootCauseSlot, ...]
    #: True quando já há mais causas raiz ativas do que o limite permite. As
    #: causas ativas mantêm a vaga (não se abandona trabalho iniciado), mas
    #: nenhuma nova causa é admitida enquanto a violação existir.
    wip_breach: bool = False

    @property
    def admitted_request_ids(self) -> tuple[str, ...]:
        return tuple(rid for slot in self.admitted for rid in slot.request_ids)

    @property
    def queued_request_ids(self) -> tuple[str, ...]:
        return tuple(rid for slot in self.queued for rid in slot.request_ids)


class WipPolicy:
    def __init__(self, max_active_root_causes: int = DEFAULT_MAX_ACTIVE_ROOT_CAUSES) -> None:
        if max_active_root_causes < 1:
            raise ValueError("max_active_root_causes deve ser >= 1")
        self._limite = max_active_root_causes

    @property
    def max_active_root_causes(self) -> int:
        return self._limite

    def plan(self, requests: list[WorkRequest]) -> AdmissionPlan:
        """Decide quais causas raiz ocupam as vagas de WIP.

        Causas que já possuem trabalho ativo mantêm a vaga: retirar a vaga de
        uma causa em andamento apenas transformaria trabalho iniciado em
        trabalho abandonado.
        """
        elegiveis = [
            req
            for req in requests
            if req.status in ACTIVE_STATUSES or req.status in {WorkRequestStatus.RECEIVED, WorkRequestStatus.QUEUED}
        ]

        por_causa: dict[str, list[WorkRequest]] = {}
        for req in elegiveis:
            por_causa.setdefault(req.root_cause_id, []).append(req)

        slots = [self._montar_slot(causa, itens) for causa, itens in por_causa.items()]
        ativas = {req.root_cause_id for req in requests if req.status in ACTIVE_STATUSES}

        slots.sort(key=self._ordem)
        em_andamento = [slot for slot in slots if slot.root_cause_id in ativas]
        candidatas = [slot for slot in slots if slot.root_cause_id not in ativas]

        vagas_livres = max(self._limite - len(em_andamento), 0)
        admitidas = tuple(em_andamento + candidatas[:vagas_livres])
        enfileiradas = tuple(candidatas[vagas_livres:])
        return AdmissionPlan(
            max_active_root_causes=self._limite,
            admitted=admitidas,
            queued=enfileiradas,
            wip_breach=len(em_andamento) > self._limite,
        )

    @staticmethod
    def _montar_slot(root_cause_id: str, itens: list[WorkRequest]) -> RootCauseSlot:
        ordenados = sorted(itens, key=lambda req: (_PRIORITY_ORDER[req.priority], req.created_at, req.request_id))
        return RootCauseSlot(
            root_cause_id=root_cause_id,
            priority=ordenados[0].priority,
            oldest_created_at=min(req.created_at for req in itens),
            request_ids=tuple(req.request_id for req in ordenados),
        )

    @staticmethod
    def _ordem(slot: RootCauseSlot) -> tuple[int, datetime, str]:
        return (_PRIORITY_ORDER[slot.priority], slot.oldest_created_at, slot.root_cause_id)
