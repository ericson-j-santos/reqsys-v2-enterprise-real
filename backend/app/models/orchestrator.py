from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OrchestratorRoutingEvent(Base):
    __tablename__ = 'orchestrator_routing_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    tema: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    coordinator_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    prioridade: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    origem: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ambiente: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdrCoordinationEvent(Base):
    __tablename__ = 'adr_coordination_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    adr_primario: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    coordinator_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    adrs_relacionados: Mapped[str] = mapped_column(Text, default='[]')
    prioridade: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    nivel_risco: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    violacoes: Mapped[str] = mapped_column(Text, default='[]')
    origem: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ambiente: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
