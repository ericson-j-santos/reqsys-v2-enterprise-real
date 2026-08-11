"""Testes da camada de transformação (extração -> contexto de renderização)."""
from datetime import date

from app.services.movimento_email.models import (
    ItemFechamento,
    ItemPendenciaCadastro,
    ItemPendenciaHistorica,
    ItemPendenciaObservacao,
)
from app.services.movimento_email.transform import montar_contexto


def test_montar_contexto_agrega_os_quatro_datasets():
    contexto = montar_contexto(
        data_referencia=date(2026, 7, 24),
        correlation_id='corr-001',
        fechamento=[ItemFechamento(indicador='Propostas', valor='120')],
        pendencias_cadastro=[
            ItemPendenciaCadastro(protocolo='P1', cliente='Fulano', cpf='11122233344', pendencia='RG', dias_em_aberto=3)
        ],
        pendencias_historicas=[
            ItemPendenciaHistorica(periodo_referencia='2026-07', pendencia='RG', quantidade=10, percentual=12.5)
        ],
        pendencias_observacao=[
            ItemPendenciaObservacao(protocolo='P2', tipo_inconsistencia='Divergência', descricao='CPF divergente')
        ],
    )

    assert contexto.data_referencia == date(2026, 7, 24)
    assert contexto.correlation_id == 'corr-001'
    assert len(contexto.fechamento) == 1
    assert len(contexto.pendencias_cadastro) == 1
    assert len(contexto.pendencias_historicas) == 1
    assert len(contexto.pendencias_observacao) == 1
    assert contexto.total_pendencias == 3


def test_montar_contexto_com_datasets_vazios():
    contexto = montar_contexto(
        data_referencia=date(2026, 7, 24),
        correlation_id='corr-002',
        fechamento=[],
        pendencias_cadastro=[],
        pendencias_historicas=[],
        pendencias_observacao=[],
    )

    assert contexto.total_pendencias == 0
    assert contexto.fechamento == []
