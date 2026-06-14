from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Requisito(Base):
    __tablename__ = 'requisitos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text)
    urgencia: Mapped[str] = mapped_column(String(20), default='media')
    area: Mapped[str] = mapped_column(String(80))
    sistema: Mapped[str] = mapped_column(String(80))
    solicitante: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default='recebido')
    impacto_regulatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
