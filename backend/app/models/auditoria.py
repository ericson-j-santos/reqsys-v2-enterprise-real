from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditoriaEvento(Base):
    __tablename__ = 'auditoria_eventos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    usuario: Mapped[str] = mapped_column(String(120))
    acao: Mapped[str] = mapped_column(String(80))
    entidade: Mapped[str] = mapped_column(String(80))
    entidade_id: Mapped[str] = mapped_column(String(80))
    payload_minimo: Mapped[str] = mapped_column(Text, default='{}')
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
