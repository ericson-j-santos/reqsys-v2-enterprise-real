from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VinculoGit(Base):
    __tablename__ = 'vinculos_git'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # código do requisito extraído do commit/PR (REQ-XXXXXXXXX)
    requisito_codigo: Mapped[str] = mapped_column(String(30), index=True)
    # id resolvido se o requisito existir no banco; NULL se veio de repo externo sem match
    requisito_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('requisitos.id', ondelete='SET NULL'), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(30))      # commit | branch | pr | merge_request | issue | tag
    provedor: Mapped[str] = mapped_column(String(20))  # github | gitlab
    repo: Mapped[str] = mapped_column(String(200))     # owner/repo
    referencia: Mapped[str] = mapped_column(String(200))  # SHA40 | número PR | nome da branch
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    titulo: Mapped[str | None] = mapped_column(Text, nullable=True)
    autor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ambiente: Mapped[str | None] = mapped_column(String(30), nullable=True)  # dev | staging | prod
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
