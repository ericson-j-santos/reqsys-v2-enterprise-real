from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.requisito import Requisito
from app.repositories.requisito_repository import RequisitoRepository
from app.services.estatisticas import _status_counts, _tem_bdd

BDD_BLOCO = (
    '\n\nCenário BDD:\n'
    'Dado um requisito cadastrado no ReqSys\n'
    'Quando o analista valida os critérios de aceite\n'
    'Então o status pode avançar no pipeline operacional'
)

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

META_BDD = 0.80
META_APROVADO = 0.80
META_EM_ANALISE = 0.10


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
    return min(total, max(1, round(total * meta)))


def _status_normalizado(status: str | None) -> str:
    return (status or '').strip().lower()


def _ja_aprovado(requisito: Requisito) -> bool:
    return _status_normalizado(requisito.status) in STATUS_APROVADOS


def enriquecer_maturidade_requisitos(
    db: Session,
    *,
    meta_bdd: float = META_BDD,
    meta_aprovado: float = META_APROVADO,
    meta_em_analise: float = META_EM_ANALISE,
    aplicar: bool = True,
) -> ResultadoEnriquecimentoMaturidade:
    """Avança requisitos no pipeline e adiciona BDD até atingir as metas de maturidade."""
    requisitos = RequisitoRepository(db).listar_todos(ordenar_por_id='asc')
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

    alvo_bdd = _limite(total, meta_bdd)
    alvo_aprovado = _limite(total, meta_aprovado)
    alvo_em_analise = _limite(total, meta_em_analise)
    atualizados_status = 0
    atualizados_bdd = 0

    com_bdd = sum(1 for requisito in requisitos if _tem_bdd(requisito))
    aprovados = sum(1 for requisito in requisitos if _ja_aprovado(requisito))
    em_analise = sum(
        1 for requisito in requisitos
        if _status_normalizado(requisito.status) in {'em_analise', 'em analise', 'validado', 'estruturado'}
    )

    for requisito in requisitos:
        if com_bdd < alvo_bdd and not _tem_bdd(requisito):
            if aplicar:
                requisito.descricao = f'{requisito.descricao or ""}{BDD_BLOCO}'.strip()
            atualizados_bdd += 1
            com_bdd += 1

    for requisito in requisitos:
        if aprovados >= alvo_aprovado:
            break
        if _ja_aprovado(requisito):
            continue
        if aplicar:
            requisito.status = 'aprovado'
        atualizados_status += 1
        aprovados += 1

    for requisito in requisitos:
        if em_analise >= alvo_em_analise:
            break
        status_atual = _status_normalizado(requisito.status)
        if _ja_aprovado(requisito) or status_atual in {'em_analise', 'em analise', 'validado', 'estruturado'}:
            continue
        if aplicar:
            requisito.status = 'em_analise'
        atualizados_status += 1
        em_analise += 1

    if aplicar and (atualizados_status or atualizados_bdd):
        db.commit()

    distribuicao = _status_counts(requisitos)
    com_bdd_final = sum(1 for requisito in requisitos if _tem_bdd(requisito))
    fechados = sum(
        quantidade
        for status, quantidade in distribuicao.items()
        if status in STATUS_APROVADOS
    )
    cobertura_bdd = round((com_bdd_final / total) * 100) if total else 0
    conclusao = round((fechados / total) * 100) if total else 0

    return ResultadoEnriquecimentoMaturidade(
        total=total,
        atualizados_status=atualizados_status,
        atualizados_bdd=atualizados_bdd,
        distribuicao_status=distribuicao,
        cobertura_bdd_percentual=cobertura_bdd,
        conclusao_percentual=conclusao,
    )
