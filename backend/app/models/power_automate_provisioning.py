from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PowerAutomateProvisioningRegistry(Base):
    """Registro governado de provisionamentos Power Automate."""

    __tablename__ = 'power_automate_provisioning_registry'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True, unique=True)
    status: Mapped[str] = mapped_column(String(40), default='planned', index=True)
    ambiente: Mapped[str] = mapped_column(String(40), default='dev', index=True)
    solution_name: Mapped[str] = mapped_column(String(120), default='ReqSysAutomacao')
    flow_id: Mapped[str] = mapped_column(String(80), default='', index=True)
    flow_display_name: Mapped[str] = mapped_column(String(200), default='')
    trigger_type: Mapped[str] = mapped_column(String(40), default='HttpRequest')
    workflow_run_url: Mapped[str] = mapped_column(Text, default='')
    artifact_url: Mapped[str] = mapped_column(Text, default='')
    executed_by: Mapped[str] = mapped_column(String(120), default='reqsys')
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    manifesto_json: Mapped[str] = mapped_column(Text, default='{}')
    dispatch_json: Mapped[str] = mapped_column(Text, default='{}')
    erro: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
