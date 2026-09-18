from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MovimentoEmailDispatch(Base):
    """Fila durável de envio do e-mail diário de Prospecção Movimento (#2861).

    Substitui a fila MongoDB descrita na documentação original pela base já
    provisionada do ReqSys, atrás da mesma porta (`MovimentoEmailQueueRepository`)
    — um adapter MongoDB pode ser plugado depois sem alterar `consumer.py`/`jobs.py`
    (ADR-001). Ver docs/architecture/movimento-email-pipeline.md.
    """

    __tablename__ = 'movimento_email_dispatch'

    id:                   Mapped[int] =             mapped_column(Integer, primary_key=True, index=True)
    correlation_id:       Mapped[str] =             mapped_column(String(120), index=True)
    data_referencia:      Mapped[date] =            mapped_column(Date, index=True)
    status:               Mapped[str] =             mapped_column(String(20), default='PENDING', index=True)
    destinatarios:        Mapped[str] =             mapped_column(Text, default='')
    assunto:              Mapped[str] =             mapped_column(String(300), default='')
    html_body:            Mapped[str] =             mapped_column(Text, default='')
    text_body:            Mapped[str] =             mapped_column(Text, default='')
    reserved_at:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count:          Mapped[int] =             mapped_column(Integer, default=0)
    max_retries:          Mapped[int] =             mapped_column(Integer, default=5)
    error_detail:         Mapped[str] =             mapped_column(Text, default='')
    sent_at:              Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:           Mapped[datetime] =        mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at:           Mapped[datetime] =        mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
