from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PromptExecutionRecord(Base):
    """Registro persistente de uma execução coordenada por ADR/PDR."""

    __tablename__ = "prompt_execution_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="planned", index=True)
    objective: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    human_approval_required: Mapped[str] = mapped_column(String(10), default="false")
    branch_name: Mapped[str] = mapped_column(String(255), default="")
    commit_sha: Mapped[str] = mapped_column(String(80), default="", index=True)
    pull_request_url: Mapped[str] = mapped_column(Text, default="")
    workflow_run_url: Mapped[str] = mapped_column(Text, default="")
    artifact_url: Mapped[str] = mapped_column(Text, default="")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
