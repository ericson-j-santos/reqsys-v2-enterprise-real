"""Fila de envio durável (porta + adapter SQLAlchemy) — ADR-001, ADR-010.

Implementa a limpeza de reservas travadas exigida para todo fluxo que
reserva registros (timeout padrão 15 min, configurável — instrução global do
usuário): `limpar_reservas_travadas` sempre roda antes de `reservar_lote`
devolver um novo lote, e registra no log quando libera algo.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.pii_masking import mascarar_email
from app.models.movimento_email_dispatch import MovimentoEmailDispatch

logger = logging.getLogger('reqsys.movimento_email.queue')

STATUS_PENDING = 'PENDING'
STATUS_PROCESSING = 'PROCESSING'
STATUS_SENT = 'SENT'
STATUS_ERROR = 'ERROR'

DEFAULT_LOTE_MAX = 20
DEFAULT_RESERVA_TIMEOUT_MINUTOS = 15
DEFAULT_MAX_TENTATIVAS = 5


def _mascarar_lista_destinatarios(destinatarios: str) -> str:
    return ', '.join(mascarar_email(e.strip()) for e in destinatarios.split(',') if e.strip())


def enfileirar(
    db: Session,
    *,
    correlation_id: str,
    data_referencia: date,
    destinatarios: list[str],
    assunto: str,
    html_body: str,
    text_body: str,
    max_retries: int = DEFAULT_MAX_TENTATIVAS,
) -> MovimentoEmailDispatch:
    item = MovimentoEmailDispatch(
        correlation_id=correlation_id,
        data_referencia=data_referencia,
        status=STATUS_PENDING,
        destinatarios=', '.join(destinatarios),
        assunto=assunto,
        html_body=html_body,
        text_body=text_body,
        max_retries=max_retries,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info(
        'movimento_email_enfileirado id=%s correlation_id=%s destinatarios=%s',
        item.id, correlation_id, _mascarar_lista_destinatarios(item.destinatarios),
    )
    return item


def limpar_reservas_travadas(
    db: Session,
    *,
    timeout_minutos: int = DEFAULT_RESERVA_TIMEOUT_MINUTOS,
) -> int:
    """Devolve para `PENDING` itens travados em `PROCESSING` além do timeout."""
    limite = datetime.now(UTC) - timedelta(minutes=timeout_minutos)
    travados = (
        db.query(MovimentoEmailDispatch)
        .filter(MovimentoEmailDispatch.status == STATUS_PROCESSING)
        .filter(MovimentoEmailDispatch.reserved_at <= limite)
        .all()
    )
    for item in travados:
        item.status = STATUS_PENDING
        item.reserved_at = None
        db.add(item)
        logger.info('movimento_email_reserva_travada_liberada id=%s correlation_id=%s', item.id, item.correlation_id)
    if travados:
        db.commit()
    return len(travados)


def reservar_lote(
    db: Session,
    *,
    lote_max: int = DEFAULT_LOTE_MAX,
) -> list[MovimentoEmailDispatch]:
    """Reserva (`PROCESSING`) até `lote_max` itens `PENDING`, mais antigos primeiro."""
    itens = (
        db.query(MovimentoEmailDispatch)
        .filter(MovimentoEmailDispatch.status == STATUS_PENDING)
        .order_by(MovimentoEmailDispatch.created_at.asc())
        .limit(lote_max)
        .all()
    )
    agora = datetime.now(UTC)
    for item in itens:
        item.status = STATUS_PROCESSING
        item.reserved_at = agora
        db.add(item)
    if itens:
        db.commit()
        for item in itens:
            db.refresh(item)
    return itens


def marcar_enviado(db: Session, item: MovimentoEmailDispatch) -> None:
    item.status = STATUS_SENT
    item.sent_at = datetime.now(UTC)
    item.error_detail = ''
    db.add(item)
    db.commit()
    logger.info('movimento_email_enviado id=%s correlation_id=%s', item.id, item.correlation_id)


def marcar_erro(db: Session, item: MovimentoEmailDispatch, detalhe: str) -> None:
    item.retry_count += 1
    item.error_detail = detalhe[:2000]
    item.reserved_at = None
    item.status = STATUS_ERROR if item.retry_count >= item.max_retries else STATUS_PENDING
    db.add(item)
    db.commit()
    logger.warning(
        'movimento_email_falha id=%s correlation_id=%s tentativa=%s status=%s',
        item.id, item.correlation_id, item.retry_count, item.status,
    )


def snapshot(db: Session) -> dict[str, int]:
    contagens = {STATUS_PENDING: 0, STATUS_PROCESSING: 0, STATUS_SENT: 0, STATUS_ERROR: 0}
    resultado = (
        db.query(MovimentoEmailDispatch.status, func.count(MovimentoEmailDispatch.id))
        .group_by(MovimentoEmailDispatch.status)
        .all()
    )
    for status, total in resultado:
        contagens[status] = total
    return contagens
