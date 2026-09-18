"""Testes da fila durável de envio — foco na limpeza de reservas travadas
(instrução global obrigatória: timeout padrão 15min, log quando libera)."""
from datetime import UTC, date, datetime, timedelta

from app.services.movimento_email import queue_repository as fila


def _enfileirar(db, correlation_id='corr-001'):
    return fila.enfileirar(
        db,
        correlation_id=correlation_id,
        data_referencia=date(2026, 7, 24),
        destinatarios=['analista@empresa.com'],
        assunto='Assunto teste',
        html_body='<p>html</p>',
        text_body='texto',
    )


def test_enfileirar_cria_item_pending(db_session):
    item = _enfileirar(db_session)

    assert item.id is not None
    assert item.status == fila.STATUS_PENDING
    assert item.destinatarios == 'analista@empresa.com'


def test_reservar_lote_marca_processing_e_reserved_at(db_session):
    _enfileirar(db_session, 'corr-1')
    _enfileirar(db_session, 'corr-2')

    lote = fila.reservar_lote(db_session, lote_max=10)

    assert len(lote) == 2
    assert all(item.status == fila.STATUS_PROCESSING for item in lote)
    assert all(item.reserved_at is not None for item in lote)


def test_reservar_lote_respeita_lote_max(db_session):
    for i in range(5):
        _enfileirar(db_session, f'corr-{i}')

    lote = fila.reservar_lote(db_session, lote_max=2)

    assert len(lote) == 2


def test_limpar_reservas_travadas_libera_apos_timeout(db_session):
    item = _enfileirar(db_session, 'corr-travado')
    item.status = fila.STATUS_PROCESSING
    item.reserved_at = datetime.now(UTC) - timedelta(minutes=20)
    db_session.add(item)
    db_session.commit()

    liberados = fila.limpar_reservas_travadas(db_session, timeout_minutos=15)

    db_session.refresh(item)
    assert liberados == 1
    assert item.status == fila.STATUS_PENDING
    assert item.reserved_at is None


def test_limpar_reservas_travadas_nao_afeta_reserva_recente(db_session):
    item = _enfileirar(db_session, 'corr-recente')
    item.status = fila.STATUS_PROCESSING
    item.reserved_at = datetime.now(UTC) - timedelta(minutes=2)
    db_session.add(item)
    db_session.commit()

    liberados = fila.limpar_reservas_travadas(db_session, timeout_minutos=15)

    db_session.refresh(item)
    assert liberados == 0
    assert item.status == fila.STATUS_PROCESSING


def test_marcar_enviado_atualiza_status_e_sent_at(db_session):
    item = _enfileirar(db_session)

    fila.marcar_enviado(db_session, item)

    assert item.status == fila.STATUS_SENT
    assert item.sent_at is not None


def test_marcar_erro_reagenda_ate_atingir_max_tentativas(db_session):
    item = fila.enfileirar(
        db_session,
        correlation_id='corr-erro',
        data_referencia=date(2026, 7, 24),
        destinatarios=['analista@empresa.com'],
        assunto='assunto',
        html_body='<p>x</p>',
        text_body='x',
        max_retries=2,
    )

    fila.marcar_erro(db_session, item, 'falha 1')
    assert item.status == fila.STATUS_PENDING
    assert item.retry_count == 1

    fila.marcar_erro(db_session, item, 'falha 2')
    assert item.status == fila.STATUS_ERROR
    assert item.retry_count == 2


def test_snapshot_conta_por_status(db_session):
    a = _enfileirar(db_session, 'corr-a')
    _enfileirar(db_session, 'corr-b')
    fila.marcar_enviado(db_session, a)

    contagens = fila.snapshot(db_session)

    assert contagens[fila.STATUS_SENT] == 1
    assert contagens[fila.STATUS_PENDING] == 1
