from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SecuritySessionState(Base):
    """Estado global de revogação de sessões humanas do ReqSys.

    O registro singleton (id=1) mantém apenas metadados de segurança. Tokens,
    segredos e identidades em claro não são persistidos aqui.
    """

    __tablename__ = 'security_session_state'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    session_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
