from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PlannerPublishAttempt(Base):
    """Tentativa de publicação governada de uma tarefa no Planner (issue #32).

    `idempotency_key` é a garantia de dedupe sob concorrência (unique+index,
    não um check-then-insert) — deriva de `source_id` (origem+demanda) mais o
    hash do payload mutável, então o mesmo pedido reenviado nunca cria uma
    segunda tarefa no Planner.
    """

    __tablename__ = 'planner_publish_attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True, default='')

    source_id: Mapped[str] = mapped_column(String(200), index=True)
    plan_id: Mapped[str] = mapped_column(String(200))
    bucket_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default='')
    due_date: Mapped[str] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(20))
    requester: Mapped[str] = mapped_column(String(200))

    status: Mapped[str] = mapped_column(String(30), index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    planner_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ultimo_erro: Mapped[str] = mapped_column(Text, default='')
