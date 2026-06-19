from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class IntegracaoLog(Base):
    __tablename__ = 'integracao_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    tipo: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    titulo: Mapped[str] = mapped_column(String(200), default='')
    autor: Mapped[str] = mapped_column(String(120), default='')
    total: Mapped[int] = mapped_column(Integer, default=0)
    mensagem: Mapped[str] = mapped_column(Text, default='')
    detalhes: Mapped[str] = mapped_column(Text, default='{}')
    correlation_id: Mapped[str] = mapped_column(String(80), default='', index=True)
