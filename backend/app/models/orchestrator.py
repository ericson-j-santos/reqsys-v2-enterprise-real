from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
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


class AgileProjectPackage(Base):
    __tablename__ = 'agile_project_packages'
    __table_args__ = (
        UniqueConstraint('package_id', name='uq_agile_project_packages_package_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    package_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default='1.0.0')
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    integration_targets_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    external_references_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )
