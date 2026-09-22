from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CdiRate(Base):
    """Cache interno governado da taxa CDI diaria publicada pelo Banco Central."""

    __tablename__ = 'cdi_rates'
    __table_args__ = (UniqueConstraint('reference_date', 'source', name='uq_cdi_rates_reference_source'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference_date: Mapped[date] = mapped_column(Date, index=True)
    daily_rate_percent: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    daily_rate_decimal: Mapped[Decimal] = mapped_column(Numeric(18, 12))
    source: Mapped[str] = mapped_column(String(80), default='bcb_sgs_12', index=True)
    source_url: Mapped[str] = mapped_column(Text, default='')
    raw_payload: Mapped[str] = mapped_column(Text, default='{}')
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
