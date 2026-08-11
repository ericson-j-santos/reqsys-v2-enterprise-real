"""Testes do consumer da fila de e-mail — dry_run nunca deve parecer,
estruturalmente, um envio real (ver histórico de correções deste projeto)."""
from datetime import UTC, date, datetime, timedelta

from app.services.movimento_email import queue_repository as fila
from app.services.movimento_email.consumer import consumir_fila_email_movimento
from app.services.movimento_email.smtp_sender import EnvioEmailError


class _FakeSenderOk:
    def __init__(self):
        self.enviados = []

    def enviar(self, message):
        self.enviados.append(message)


class _FakeSenderFalha:
    def enviar(self, message):
        raise EnvioEmailError('falha simulada de SMTP')


def _enfileirar(db, correlation_id='corr-001', max_retries=5):
    return fila.enfileirar(
        db,
        correlation_id=correlation_id,
        data_referencia=date(2026, 7, 24),
        destinatarios=['analista@empresa.com'],
        assunto='Assunto teste',
        html_body='<p>html</p>',
        text_body='texto',
        max_retries=max_retries,
    )


def test_dry_run_nao_envia_nem_marca_e_tem_formato_distinto(db_session):
    _enfileirar(db_session)
    sender = _FakeSenderOk()

    resultado = consumir_fila_email_movimento(db_session, sender, remetente='robo@empresa.com', dry_run=True)

    assert resultado['dry_run'] is True
    assert 'enviados' not in resultado
    assert 'falhas' not in resultado
    assert resultado['total_pendentes_no_lote'] == 1
    assert sender.enviados == []


def test_consumo_real_envia_e_marca_sent(db_session):
    _enfileirar(db_session)
    sender = _FakeSenderOk()

    resultado = consumir_fila_email_movimento(db_session, sender, remetente='robo@empresa.com', dry_run=False)

    assert resultado['dry_run'] is False
    assert resultado['enviados'] == 1
    assert resultado['falhas'] == 0
    assert len(sender.enviados) == 1


def test_consumo_com_falha_marca_erro_e_incrementa_retry(db_session):
    _enfileirar(db_session, max_retries=5)
    sender = _FakeSenderFalha()

    resultado = consumir_fila_email_movimento(db_session, sender, remetente='robo@empresa.com', dry_run=False)

    assert resultado['falhas'] == 1
    assert resultado['itens'][0]['status'] == fila.STATUS_PENDING
    assert resultado['itens'][0]['tentativas'] == 1


def test_consumo_libera_reservas_travadas_antes_de_reservar_novo_lote(db_session):
    travado = _enfileirar(db_session, 'corr-travado')
    travado.status = fila.STATUS_PROCESSING
    travado.reserved_at = datetime.now(UTC) - timedelta(minutes=30)
    db_session.add(travado)
    db_session.commit()

    sender = _FakeSenderOk()
    resultado = consumir_fila_email_movimento(db_session, sender, remetente='robo@empresa.com', dry_run=False)

    assert resultado['reservas_liberadas'] == 1
    assert resultado['enviados'] == 1
