from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CopilotMemoryRecord(Base):
    """Memória persistente governada entre ReqSys, Planner, Excel e Copilot.

    `content_hash` representa somente o conteúdo efetivo. Origem e sinais de
    sincronização ficam fora do hash para que ecos Planner -> ReqSys não gerem
    nova versão nem comandos de retorno ao Planner.
    """

    __tablename__ = 'copilot_memory_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    planner_task_id: Mapped[str | None] = mapped_column(String(200), unique=True, index=True, nullable=True)

    assunto: Mapped[str] = mapped_column(String(500), default='')
    contexto: Mapped[str] = mapped_column(Text, default='')
    estado_atual: Mapped[str] = mapped_column(Text, default='')
    decisao: Mapped[str] = mapped_column(Text, default='')
    pendencia: Mapped[str] = mapped_column(Text, default='')
    proximo_passo: Mapped[str] = mapped_column(Text, default='')
    fonte_url: Mapped[str] = mapped_column(Text, default='')
    data_fonte: Mapped[str] = mapped_column(String(40), default='')
    validade: Mapped[str] = mapped_column(String(30), default='ativa', index=True)

    planner_titulo: Mapped[str] = mapped_column(String(500), default='')
    planner_status: Mapped[str] = mapped_column(String(50), default='')
    planner_percentual: Mapped[int] = mapped_column(Integer, default=0)
    planner_prazo: Mapped[str] = mapped_column(String(40), default='')

    ultima_origem: Mapped[str] = mapped_column(String(30), default='reqsys', index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str] = mapped_column(String(80), default='', index=True)

    atualizar_planner: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    planner_sync_status: Mapped[str] = mapped_column(String(30), default='nao_solicitado', index=True)
    planner_applied_hash: Mapped[str] = mapped_column(String(64), default='')
    ultimo_erro: Mapped[str] = mapped_column(Text, default='')


class CopilotMemoryHistory(Base):
    """Histórico imutável de alterações reais da memória."""

    __tablename__ = 'copilot_memory_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    memory_id: Mapped[str] = mapped_column(String(64), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    origem: Mapped[str] = mapped_column(String(30), index=True)
    correlation_id: Mapped[str] = mapped_column(String(80), default='', index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
