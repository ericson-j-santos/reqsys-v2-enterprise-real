"""Métricas operacionais da Central.

A métrica que importa não é commit nem PR verde: é **Lead Time to Evidence** —
o tempo entre a solicitação entrar e existir evidência completa no SHA corrente.
As demais séries existem para explicar onde esse tempo é gasto: quanto está
parado por bloqueio, quanto está represado pelo limite de WIP e quanto rodou mas
não foi comprovado.

O lead time é medido do ``created_at`` da solicitação até o ``recorded_at`` do
registro de evidência que a tornou ``EVIDENCED`` — não até o ``updated_at``, que
qualquer escrita posterior moveria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from app.domain.central.evidence_ledger import EvidenceRecord, EvidenceStatus
from app.domain.central.models import (
    ACTIVE_STATUSES,
    ExecutorKind,
    WorkRequest,
    WorkRequestStatus,
    agora,
)
from app.domain.central.wip_policy import AdmissionPlan


@dataclass(frozen=True)
class LeadTimeToEvidence:
    """Distribuição do tempo até evidência, em segundos."""

    amostras: int
    p50_segundos: float | None = None
    p95_segundos: float | None = None
    maximo_segundos: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "amostras": self.amostras,
            "p50_segundos": self.p50_segundos,
            "p95_segundos": self.p95_segundos,
            "maximo_segundos": self.maximo_segundos,
        }


@dataclass(frozen=True)
class CentralMetrics:
    total: int
    por_status: dict[str, int] = field(default_factory=dict)
    por_executor: dict[str, int] = field(default_factory=dict)
    evidencia_por_status: dict[str, int] = field(default_factory=dict)
    causas_raiz_ativas: int = 0
    causas_raiz_enfileiradas: int = 0
    max_causas_raiz_ativas: int = 0
    wip_breach: bool = False
    bloqueadas: int = 0
    #: Bloqueios agrupados por causa, para atacar a raiz e não o sintoma.
    bloqueios_por_causa: dict[str, int] = field(default_factory=dict)
    aguardando_evidencia: int = 0
    #: Verificações que mais impedem a conclusão, entre as que faltam.
    verificacoes_pendentes: dict[str, int] = field(default_factory=dict)
    idade_maxima_aguardando_evidencia_segundos: float | None = None
    lead_time_to_evidence: LeadTimeToEvidence = field(
        default_factory=lambda: LeadTimeToEvidence(amostras=0)
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "por_status": self.por_status,
            "por_executor": self.por_executor,
            "evidencia_por_status": self.evidencia_por_status,
            "wip": {
                "causas_raiz_ativas": self.causas_raiz_ativas,
                "causas_raiz_enfileiradas": self.causas_raiz_enfileiradas,
                "max_causas_raiz_ativas": self.max_causas_raiz_ativas,
                "breach": self.wip_breach,
            },
            "bloqueios": {
                "total": self.bloqueadas,
                "por_causa": self.bloqueios_por_causa,
            },
            "aguardando_evidencia": {
                "total": self.aguardando_evidencia,
                "verificacoes_pendentes": self.verificacoes_pendentes,
                "idade_maxima_segundos": self.idade_maxima_aguardando_evidencia_segundos,
            },
            "lead_time_to_evidence": self.lead_time_to_evidence.to_dict(),
        }


def percentil(valores: list[float], fracao: float) -> float | None:
    """Percentil por interpolação linear; ``None`` quando não há amostra."""
    if not valores:
        return None
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return round(ordenados[0], 3)
    posicao = fracao * (len(ordenados) - 1)
    inferior = int(posicao)
    superior = min(inferior + 1, len(ordenados) - 1)
    peso = posicao - inferior
    return round(ordenados[inferior] * (1 - peso) + ordenados[superior] * peso, 3)


def calcular_metricas(
    solicitacoes: list[WorkRequest],
    evidencias: dict[str, EvidenceRecord],
    plano: AdmissionPlan,
) -> CentralMetrics:
    momento = agora()
    por_status: dict[str, int] = {}
    por_executor: dict[str, int] = {}
    evidencia_por_status: dict[str, int] = {}
    bloqueios: dict[str, int] = {}
    pendentes: dict[str, int] = {}
    lead_times: list[float] = []
    idades_aguardando: list[float] = []
    bloqueadas = 0
    aguardando = 0

    for solicitacao in solicitacoes:
        por_status[solicitacao.status.value] = por_status.get(solicitacao.status.value, 0) + 1
        por_executor[solicitacao.executor.value] = por_executor.get(solicitacao.executor.value, 0) + 1

        registro = evidencias.get(solicitacao.request_id)
        if registro is not None:
            evidencia_por_status[registro.status.value] = (
                evidencia_por_status.get(registro.status.value, 0) + 1
            )

        if solicitacao.status is WorkRequestStatus.BLOCKED:
            bloqueadas += 1
            causa = _causa(solicitacao.blocker)
            bloqueios[causa] = bloqueios.get(causa, 0) + 1

        if solicitacao.status is WorkRequestStatus.AWAITING_EVIDENCE:
            aguardando += 1
            idades_aguardando.append(_segundos(momento - solicitacao.created_at))
            if registro is not None:
                for check in registro.missing_checks:
                    pendentes[check.value] = pendentes.get(check.value, 0) + 1

        if solicitacao.status is WorkRequestStatus.EVIDENCED and registro is not None:
            # Só conta quando a evidência é do SHA corrente: evidência de outro
            # SHA não comprova esta versão e mediria um lead time fictício.
            if registro.status is EvidenceStatus.EVIDENCED and (
                solicitacao.sha is None or registro.sha == solicitacao.sha
            ):
                lead_times.append(_segundos(registro.recorded_at - solicitacao.created_at))

    ativas = {
        solicitacao.root_cause_id
        for solicitacao in solicitacoes
        if solicitacao.status in ACTIVE_STATUSES
    }

    return CentralMetrics(
        total=len(solicitacoes),
        por_status=dict(sorted(por_status.items())),
        por_executor=dict(sorted(por_executor.items())),
        evidencia_por_status=dict(sorted(evidencia_por_status.items())),
        causas_raiz_ativas=len(ativas),
        causas_raiz_enfileiradas=len(plano.queued),
        max_causas_raiz_ativas=plano.max_active_root_causes,
        wip_breach=plano.wip_breach,
        bloqueadas=bloqueadas,
        bloqueios_por_causa=dict(sorted(bloqueios.items(), key=lambda item: (-item[1], item[0]))),
        aguardando_evidencia=aguardando,
        verificacoes_pendentes=dict(sorted(pendentes.items(), key=lambda item: (-item[1], item[0]))),
        idade_maxima_aguardando_evidencia_segundos=(
            round(max(idades_aguardando), 3) if idades_aguardando else None
        ),
        lead_time_to_evidence=LeadTimeToEvidence(
            amostras=len(lead_times),
            p50_segundos=percentil(lead_times, 0.5),
            p95_segundos=percentil(lead_times, 0.95),
            maximo_segundos=round(max(lead_times), 3) if lead_times else None,
        ),
    )


def _causa(blocker: str | None) -> str:
    """Agrupa pelo prefixo antes de ``:`` — a causa, não a instância."""
    if not blocker:
        return "nao_informado"
    return blocker.split(":", 1)[0]


def _segundos(delta: timedelta) -> float:
    return round(max(delta.total_seconds(), 0.0), 3)


#: Executores conhecidos, para o painel mostrar zero em vez de omitir a linha.
EXECUTORES_CONHECIDOS = tuple(item.value for item in ExecutorKind)
