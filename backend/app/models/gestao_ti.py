from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def novo_servico_id() -> str:
    return str(uuid.uuid4())


class ServicoTI(Base):
    __tablename__ = 'gestao_ti_servicos'

    servico_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=novo_servico_id)
    codigo: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    criticidade: Mapped[str] = mapped_column(String(20), nullable=False, default='media')
    responsavel_tecnico: Mapped[str] = mapped_column(String(200), nullable=False)
    responsavel_negocio: Mapped[str] = mapped_column(String(200), nullable=False)
    versao_catalogo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    requisitos: Mapped[list['RequisitoServico']] = relationship(
        back_populates='servico',
        cascade='all, delete-orphan',
    )


class RequisitoServico(Base):
    __tablename__ = 'gestao_ti_requisito_servico'
    __table_args__ = (
        UniqueConstraint('requisito_id', name='uq_gestao_ti_requisito_servico_requisito'),
    )

    vinculo_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requisito_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('requisitos.id'),
        nullable=False,
        index=True,
    )
    servico_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('gestao_ti_servicos.servico_id'),
        nullable=False,
        index=True,
    )
    criado_por: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    servico: Mapped[ServicoTI] = relationship(back_populates='requisitos')
