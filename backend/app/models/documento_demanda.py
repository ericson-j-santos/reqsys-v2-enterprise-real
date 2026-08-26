from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DocumentoDemandaAnalise(Base):
    __tablename__ = 'documento_demanda_analises'
    __table_args__ = (UniqueConstraint('demanda_ref', 'sha256', name='uq_documento_demanda_sha256'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demanda_ref: Mapped[str] = mapped_column(String(120), index=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default='RECEBIDO', index=True)
    texto_extraido: Mapped[str] = mapped_column(Text, default='')
    candidatos_json: Mapped[str] = mapped_column(Text, default='[]')
    erro: Mapped[str] = mapped_column(Text, default='')
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
