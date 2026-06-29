from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.requisito import Requisito

STATUS_APROVADOS = frozenset({
    'aprovado',
    'aprovados',
    'concluido',
    'concluído',
    'concluida',
    'done',
    'finalizado',
    'implementado',
    'encerrado',
})

STATUS_EM_ANALISE = frozenset({
    'em_analise',
    'em analise',
    'validado',
    'estruturado',
})

STATUS_REJEITADOS = frozenset({
    'rejeitado',
    'rejeitados',
    'cancelado',
})


def _status_normalizado(status: str | None) -> str:
    return (status or '').strip().lower()


def calcular_metricas_requisitos(db: Session) -> dict[str, int]:
    """Métricas canônicas do pipeline de requisitos para dashboard e analytics."""
    total = db.query(Requisito).count()
    if total == 0:
        return {
            'total': 0,
            'em_analise': 0,
            'aprovados': 0,
            'rejeitados': 0,
            'pendentes': 0,
        }

    aprovados = (
        db.query(Requisito)
        .filter(func.lower(Requisito.status).in_(STATUS_APROVADOS))
        .count()
    )
    em_analise = (
        db.query(Requisito)
        .filter(
            func.lower(Requisito.status).in_(STATUS_EM_ANALISE)
            | func.lower(Requisito.status).like('%analise%')
        )
        .count()
    )
    rejeitados = (
        db.query(Requisito)
        .filter(func.lower(Requisito.status).in_(STATUS_REJEITADOS))
        .count()
    )
    pendentes = max(total - aprovados - em_analise - rejeitados, 0)

    return {
        'total': total,
        'em_analise': em_analise,
        'aprovados': aprovados,
        'rejeitados': rejeitados,
        'pendentes': pendentes,
    }
