from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.requisito_repository import RequisitoRepository

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
    # 'backlog' e alcancado via POST /v1/backlog/publicar-redmine apos 'estruturado'
    # (app/api/pipeline.py) — e um estagio mais avancado do pipeline, nao um item
    # intocado; contar como pendente penalizava requisitos ja triados e publicados.
    'backlog',
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
    repo = RequisitoRepository(db)
    total = repo.contar_total()
    if total == 0:
        return {
            'total': 0,
            'em_analise': 0,
            'aprovados': 0,
            'rejeitados': 0,
            'pendentes': 0,
        }

    aprovados = repo.contar_por_status_in(STATUS_APROVADOS)
    em_analise = repo.contar_por_status_in_ou_contendo(STATUS_EM_ANALISE, 'analise')
    rejeitados = repo.contar_por_status_in(STATUS_REJEITADOS)
    pendentes = max(total - aprovados - em_analise - rejeitados, 0)

    return {
        'total': total,
        'em_analise': em_analise,
        'aprovados': aprovados,
        'rejeitados': rejeitados,
        'pendentes': pendentes,
    }
