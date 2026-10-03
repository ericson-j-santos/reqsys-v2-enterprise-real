from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ServiceToken(Base):
    """Token S2S escopado para rotas admin (mesmo padrao do VaultToken/ADR-041,
    generalizado para alem do cofre) — permite pipelines/automacoes chamarem
    rotas `require_admin` sem um login humano, restritas a escopos explicitos.
    """

    __tablename__ = 'service_tokens'

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scopes: Mapped[str] = mapped_column(Text, default='[]')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
