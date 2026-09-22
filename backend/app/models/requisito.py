from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Requisito(Base):
    __tablename__ = 'requisitos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text)
    urgencia: Mapped[str] = mapped_column(String(20), default='media')
    area: Mapped[str] = mapped_column(String(80))
    sistema: Mapped[str] = mapped_column(String(80))
    solicitante: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default='recebido')
    impacto_regulatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recomendacoes_ia: Mapped[list['RecommendationIA']] = relationship(
        back_populates='requisito',
        cascade='all, delete-orphan',
    )


class RecommendationIA(Base):
    __tablename__ = 'recommendation_ia'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requisito_id: Mapped[int] = mapped_column(Integer, ForeignKey('requisitos.id'), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    contexto_incidente: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_recomendacao: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confianca_ia: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    recomendacao: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score_inicial: Mapped[float | None] = mapped_column(Float, nullable=True)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    requisito: Mapped[Requisito] = relationship(back_populates='recomendacoes_ia')
    decisao: Mapped['RecommendationIADecision | None'] = relationship(
        back_populates='recomendacao',
        uselist=False,
        cascade='all, delete-orphan',
    )
    outcome: Mapped['RecommendationIAOutcome | None'] = relationship(
        back_populates='recomendacao',
        uselist=False,
        cascade='all, delete-orphan',
    )


class RecommendationIADecision(Base):
    __tablename__ = 'recommendation_ia_decision'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recomendacao_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('recommendation_ia.id'),
        unique=True,
        nullable=False,
        index=True,
    )
    aceita: Mapped[bool] = mapped_column(Boolean, nullable=False)
    motivo_decisao: Mapped[str | None] = mapped_column(Text, nullable=True)
    decidido_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decidido_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    recomendacao: Mapped[RecommendationIA] = relationship(back_populates='decisao')


class RecommendationIAOutcome(Base):
    __tablename__ = 'recommendation_ia_outcome'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recomendacao_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('recommendation_ia.id'),
        unique=True,
        nullable=False,
        index=True,
    )
    foi_aplicada: Mapped[bool] = mapped_column(Boolean, nullable=False)
    versao_aplicada: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome_positivo: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    score_pos_correcao: Mapped[float | None] = mapped_column(Float, nullable=True)
    avaliado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    recomendacao: Mapped[RecommendationIA] = relationship(back_populates='outcome')
