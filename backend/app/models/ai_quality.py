from sqlalchemy import DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class QualidadeIASnapshot(Base):
    __tablename__ = 'qualidade_ia_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_geral: Mapped[float] = mapped_column(Float)
    acuracia: Mapped[float] = mapped_column(Float)
    relevancia: Mapped[float] = mapped_column(Float)
    consistencia: Mapped[float] = mapped_column(Float)
    seguranca: Mapped[float] = mapped_column(Float)
    cobertura_dados: Mapped[float] = mapped_column(Float)
    incidentes_criticos: Mapped[int] = mapped_column(Integer, default=0)
    amostra_total: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
