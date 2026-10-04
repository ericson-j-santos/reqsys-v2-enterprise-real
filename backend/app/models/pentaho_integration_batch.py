from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PentahoIntegrationBatch(Base):
    """Lote durável recebido do Pentaho.

    A chave de idempotência possui restrição única para garantir deduplicação
    também quando duas requisições concorrentes tentam criar o mesmo lote.
    O payload é armazenado como texto JSON para manter portabilidade entre
    SQLite (testes) e SQL Server/PostgreSQL (ambientes).
    """

    __tablename__ = 'pentaho_integration_batches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    processado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lote_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    lote_externo: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)

    origem: Mapped[str] = mapped_column(String(64), default='PENTAHO')
    processo: Mapped[str] = mapped_column(String(120), index=True)
    versao_entrada: Mapped[int] = mapped_column(Integer, default=1)
    data_referencia: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(30), default='PENDENTE', index=True)
    registros_recebidos: Mapped[int] = mapped_column(Integer, default=0)
    registros_aceitos: Mapped[int] = mapped_column(Integer, default=0)
    registros_rejeitados: Mapped[int] = mapped_column(Integer, default=0)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)

    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
