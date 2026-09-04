from uuid import uuid4

import pytest

import app.services.pentaho_integration as servico
from app.schemas.pentaho_integration import PentahoLoteEntrada
from app.services.pentaho_integration import (
    STATUS_CONCLUIDO,
    criar_ou_obter_lote,
    processar_lote_por_id,
    recuperar_lotes_abandonados,
)


def _entrada(registros=None) -> PentahoLoteEntrada:
    return PentahoLoteEntrada(
        origem='PENTAHO',
        processo='TESTE_INTEGRACAO_SERVICO',
        versaoEntrada=1,
        dataReferencia='2026-09-03',
        lote=f'lote-{uuid4()}',
        registros=registros if registros is not None else [{'produto': 10001, 'canal': 'WEB'}],
    )


def test_corrida_de_idempotencia_e_resolvida_via_integrity_error(db_session, monkeypatch):
    """Duas requisições com a mesma Idempotency-Key podem checar 'não existe'
    antes que a outra confirme o INSERT. A segunda deve colidir na restrição
    única e recuperar a linha vencedora, não propagar o erro nem duplicar."""
    idempotency_key = f'idem-{uuid4()}'
    correlation_id = f'corr-{uuid4()}'
    entrada = _entrada()

    vencedora, duplicado_inicial = criar_ou_obter_lote(db_session, entrada, idempotency_key, correlation_id)
    assert duplicado_inicial is False

    busca_original = servico._buscar_lote_por_idempotencia
    chamadas = {'n': 0}

    def busca_fingindo_corrida(db, chave):
        chamadas['n'] += 1
        if chamadas['n'] == 1:
            return None  # janela de corrida: finge não ter visto a linha vencedora ainda
        return busca_original(db, chave)

    monkeypatch.setattr(servico, '_buscar_lote_por_idempotencia', busca_fingindo_corrida)

    resultado, duplicado = servico.criar_ou_obter_lote(db_session, entrada, idempotency_key, correlation_id)

    assert duplicado is True
    assert resultado.lote_id == vencedora.lote_id
    assert chamadas['n'] == 2


def test_lote_com_registros_mistos_aceita_parcialmente(db_session):
    """registros_aceitos/registros_rejeitados existem para o caso comum de um
    lote com alguns registros válidos e outros vazios — não só tudo-ou-nada."""
    lote, _ = criar_ou_obter_lote(
        db_session,
        _entrada(registros=[{'produto': 1}, {}, {'produto': 2}, {}]),
        idempotency_key=f'idem-{uuid4()}',
        correlation_id=f'corr-{uuid4()}',
    )

    processado = processar_lote_por_id(db_session, lote.lote_id)

    assert processado is True
    db_session.refresh(lote)
    assert lote.status == STATUS_CONCLUIDO
    assert lote.registros_recebidos == 4
    assert lote.registros_aceitos == 2
    assert lote.registros_rejeitados == 2


@pytest.mark.parametrize('kwargs', [{'timeout_segundos': 0}, {'timeout_segundos': -1}])
def test_recuperar_lotes_abandonados_rejeita_timeout_invalido(db_session, kwargs):
    with pytest.raises(ValueError, match='timeout_segundos'):
        recuperar_lotes_abandonados(db_session, max_tentativas=5, **kwargs)


@pytest.mark.parametrize('kwargs', [{'max_tentativas': 0}, {'max_tentativas': -1}])
def test_recuperar_lotes_abandonados_rejeita_max_tentativas_invalido(db_session, kwargs):
    with pytest.raises(ValueError, match='max_tentativas'):
        recuperar_lotes_abandonados(db_session, timeout_segundos=300, **kwargs)
