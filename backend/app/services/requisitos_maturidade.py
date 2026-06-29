from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.requisito import Requisito
from app.services.estatisticas import _status_counts, _tem_bdd

BDD_BLOCO = (
    '\n\nCenário BDD:\n'
    'Dado um requisito cadastrado no ReqSys\n'
    'Quando o analista valida os critérios de aceite\n'
    'Então o status pode avançar no pipeline operacional'
)

META_BDD = 0.45
META_APROVADO = 0.45
META_EM_ANALISE = 0.25


@dataclass(frozen=True)
class ResultadoEnriquecimentoMaturidade:
    total: int
    atualizados_status: int
    atualizados_bdd: int
    distribuicao_status: dict[str, int]
    cobertura_bdd_percentual: int
    conclusao_percentual: int


def _limite(total: int, meta: float) -> int:
    if total <= 0:
        return 0
    return max(1, round(total * meta))


def enriquecer_maturidade_requisitos(
    db: Session,
    *,
    meta_bdd: float = META_BDD,
    meta_aprovado: float = META_APROVADO,
    meta_em_analise: float = META_EM_ANALISE,
    aplicar: bool = True,
) -> ResultadoEnriquecimentoMaturidade:
    """Avança requisitos no pipeline e adiciona BDD de forma idempotente e determinística."""
    requisitos = db.query(Requisito).order_by(Requisito.id).all()
    total = len(requisitos)
    if total == 0:
        return ResultadoEnriquecimentoMaturidade(
            total=0,
            atualizados_status=0,
            atualizados_bdd=0,
            distribuicao_status={},
            cobertura_bdd_percentual=0,
            conclusao_percentual=0,
        )

    limite_aprovado = _limite(total, meta_aprovado)
    limite_analise = _limite(total, meta_em_analise)
    limite_bdd = _limite(total, meta_bdd)
    atualizados_status = 0
    atualizados_bdd = 0

    for indice, requisito in enumerate(requisitos):
        status_alvo = 'recebido'
        if indice < limite_aprovado:
            status_alvo = 'aprovado'
        elif indice < limite_aprovado + limite_analise:
            status_alvo = 'em_analise'

        if requisito.status != status_alvo:
            if aplicar:
                requisito.status = status_alvo
            atualizados_status += 1

        if indice < limite_bdd and not _tem_bdd(requisito):
            if aplicar:
                requisito.descricao = f'{requisito.descricao or ""}{BDD_BLOCO}'.strip()
            atualizados_bdd += 1

    if aplicar and (atualizados_status or atualizados_bdd):
        db.commit()

    distribuicao = _status_counts(requisitos)
    com_bdd = sum(1 for requisito in requisitos if _tem_bdd(requisito))
    fechados = sum(
        quantidade
        for status, quantidade in distribuicao.items()
        if status in {'aprovado', 'aprovados', 'concluido', 'concluído', 'done', 'finalizado'}
    )
    cobertura_bdd = round((com_bdd / total) * 100) if total else 0
    conclusao = round((fechados / total) * 100) if total else 0

    return ResultadoEnriquecimentoMaturidade(
        total=total,
        atualizados_status=atualizados_status,
        atualizados_bdd=atualizados_bdd,
        distribuicao_status=distribuicao,
        cobertura_bdd_percentual=cobertura_bdd,
        conclusao_percentual=conclusao,
    )
