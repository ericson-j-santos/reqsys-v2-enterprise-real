"""Testes do job diário (extração -> transformação -> renderização -> fila)."""
from datetime import date

import pytest

from app.services.movimento_email import queue_repository as fila
from app.services.movimento_email.jobs import executar_job_diario
from app.services.movimento_email.models import ItemFechamento, ItemPendenciaCadastro
from app.services.movimento_email.repository import ExtracaoError


class _FakeRepository:
    def __init__(self, falhar: bool = False):
        self._falhar = falhar

    def get_fechamento(self, data_referencia):
        if self._falhar:
            raise ExtracaoError('origem indisponível')
        return [ItemFechamento(indicador='Propostas', valor='10')]

    def get_pendencias_cadastro(self, data_referencia):
        return [ItemPendenciaCadastro(protocolo='P1', cliente='Fulano', cpf='11122233344', pendencia='RG', dias_em_aberto=2)]

    def get_pendencias_historicas(self, data_referencia):
        return []

    def get_pendencias_observacao(self, data_referencia):
        return []


def test_executar_job_diario_enfileira_email_renderizado(db_session):
    resultado = executar_job_diario(
        db_session,
        _FakeRepository(),
        data_referencia=date(2026, 7, 24),
        correlation_id='corr-job-001',
        destinatarios=['analista@empresa.com'],
    )

    assert resultado['total_fechamento'] == 1
    assert resultado['total_pendencias'] == 1
    assert resultado['status'] == fila.STATUS_PENDING

    contagens = fila.snapshot(db_session)
    assert contagens[fila.STATUS_PENDING] == 1


def test_executar_job_diario_propaga_erro_de_extracao_sem_enfileirar(db_session):
    with pytest.raises(ExtracaoError):
        executar_job_diario(
            db_session,
            _FakeRepository(falhar=True),
            data_referencia=date(2026, 7, 24),
            correlation_id='corr-job-002',
            destinatarios=['analista@empresa.com'],
        )

    contagens = fila.snapshot(db_session)
    assert contagens[fila.STATUS_PENDING] == 0
