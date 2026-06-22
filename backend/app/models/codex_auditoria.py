from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CodexAuditoria(Base):
    __tablename__ = 'codex_auditoria'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    usuario: Mapped[str] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    bloqueado: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[str] = mapped_column(String(120), default='')
    fingerprint: Mapped[str] = mapped_column(String(80), index=True, default='')
    latencia_ms: Mapped[int] = mapped_column(Integer, default=0)
    reqsys_publicado: Mapped[bool] = mapped_column(Boolean, default=False)
    score_confianca: Mapped[int] = mapped_column(Integer, default=0)
    contexto_resumo: Mapped[str] = mapped_column(Text, default='')
    resultado_resumo: Mapped[str] = mapped_column(Text, default='')
    detalhes: Mapped[str] = mapped_column(Text, default='{}')
