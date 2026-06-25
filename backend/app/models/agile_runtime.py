from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AgileSprint(Base):
    __tablename__ = 'agile_sprints'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    objetivo: Mapped[str] = mapped_column(Text, nullable=False)
    data_inicio: Mapped[str] = mapped_column(Date, nullable=False)
    data_fim: Mapped[str] = mapped_column(Date, nullable=False)
    capacidade_pontos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pontos_comprometidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pontos_concluidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default='planejada', index=True, nullable=False)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    itens: Mapped[list['AgileWorkItem']] = relationship(back_populates='sprint')


class AgileWorkItem(Base):
    __tablename__ = 'agile_work_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(220), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default='novo', index=True, nullable=False)
    prioridade: Mapped[str] = mapped_column(String(10), default='P2', index=True, nullable=False)
    pontos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valor_negocio: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_risco: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_ai: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    requisito_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('requisitos.id'), nullable=True, index=True)
    sprint_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('agile_sprints.id'), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('agile_work_items.id'), nullable=True, index=True)
    criterios_aceite: Mapped[str | None] = mapped_column(Text, nullable=True)
    repositorio: Mapped[str | None] = mapped_column(String(220), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(160), nullable=True)
    change_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    change_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    change_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ci_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ci_run_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ci_status: Mapped[str] = mapped_column(String(30), default='unknown', index=True, nullable=False)
    ci_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ambiente_deploy: Mapped[str] = mapped_column(String(30), default='none', index=True, nullable=False)
    deploy_status: Mapped[str] = mapped_column(String(30), default='not_started', index=True, nullable=False)
    deploy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    sprint: Mapped[AgileSprint | None] = relationship(back_populates='itens')
    evidencias: Mapped[list['AgileEvidence']] = relationship(back_populates='work_item', cascade='all, delete-orphan')


class AgileEvidence(Base):
    __tablename__ = 'agile_evidences'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_item_id: Mapped[int] = mapped_column(Integer, ForeignKey('agile_work_items.id'), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(220), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='registrada', index=True, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    criado_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    work_item: Mapped[AgileWorkItem] = relationship(back_populates='evidencias')
