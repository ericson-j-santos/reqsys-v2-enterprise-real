from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class IntegracaoFigmaGithub(Base):
    __tablename__ = 'integracoes_figma_github'
    __table_args__ = (
        UniqueConstraint('figma_file_key', 'figma_node_id', 'figma_comment_id', 'github_repo', name='uq_figma_github_origem'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    figma_file_key: Mapped[str] = mapped_column(String(120), index=True)
    figma_node_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    figma_comment_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    github_repo: Mapped[str] = mapped_column(String(200), index=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_kind: Mapped[str] = mapped_column(String(30), default='comment')
    last_figma_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_github_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='synced', index=True)
    conflict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
