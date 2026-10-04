"""Transformação: agrega os 4 datasets extraídos em um `ContextoEmailMovimento`
pronto para renderização (ADR-001 — função pura, sem I/O).
"""

from __future__ import annotations

from datetime import date

from app.services.movimento_email.models import (
    ContextoEmailMovimento,
    ItemFechamento,
    ItemPendenciaCadastro,
    ItemPendenciaHistorica,
    ItemPendenciaObservacao,
)


def montar_contexto(
    *,
    data_referencia: date,
    correlation_id: str,
    fechamento: list[ItemFechamento],
    pendencias_cadastro: list[ItemPendenciaCadastro],
    pendencias_historicas: list[ItemPendenciaHistorica],
    pendencias_observacao: list[ItemPendenciaObservacao],
) -> ContextoEmailMovimento:
    """Monta o contexto do e-mail a partir dos datasets já extraídos.

    Não reordena nem filtra — a ordenação de negócio já vem do SQL de origem
    (ver `sql/*.sql`); esta função só agrega em um único objeto imutável.
    """
    return ContextoEmailMovimento(
        data_referencia=data_referencia,
        correlation_id=correlation_id,
        fechamento=list(fechamento),
        pendencias_cadastro=list(pendencias_cadastro),
        pendencias_historicas=list(pendencias_historicas),
        pendencias_observacao=list(pendencias_observacao),
    )
