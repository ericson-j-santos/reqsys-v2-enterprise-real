from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TeamsNotificationRecipient(Base):
    """Destinatario dinamico associado a uma politica logica de notificacao Teams."""

    __tablename__ = 'teams_notification_recipients'
    __table_args__ = (
        UniqueConstraint(
            'politica',
            'destino_tipo',
            'destino_id',
            name='uq_teams_notification_recipient_policy_destination',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    politica: Mapped[str] = mapped_column(String(120), index=True)
    nome: Mapped[str] = mapped_column(String(200), default='')
    destino_id: Mapped[str] = mapped_column(String(500))
    destino_tipo: Mapped[str] = mapped_column(String(30), default='chat')
    prioridade: Mapped[int] = mapped_column(Integer, default=100, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    observacao: Mapped[str] = mapped_column(String(500), default='')
