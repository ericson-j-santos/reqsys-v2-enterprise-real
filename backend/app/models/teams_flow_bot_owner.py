from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TeamsFlowBotOwner(Base):
    """Dono de um flow do Power Automate ("Chat with Flow bot") usado pelo canal flow_bot.

    Cada linha e um flow independente, autorizado manualmente por um funcionario
    diferente. O gateway tenta em ordem de prioridade e faz failover automatico
    quando um flow falha (ex.: desligado porque o dono esta de ferias/licenca ou
    saiu da empresa) — resolve o caso descrito pelo usuario de flows que quebram
    quando o dono fica indisponivel.
    """

    __tablename__ = 'teams_flow_bot_owners'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    owner_email: Mapped[str] = mapped_column(String(200))
    webhook_url: Mapped[str] = mapped_column(String(2000))
    prioridade: Mapped[int] = mapped_column(Integer, default=100, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    observacao: Mapped[str] = mapped_column(String(500), default='')
