from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.encrypted_text import EncryptedText
from app.db import Base


class AIConversation(Base):
    """Conversa de IA independente de dispositivo e provedor."""

    __tablename__ = 'ai_conversations'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    model: Mapped[str] = mapped_column(String(160))
    provider_conversation_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    titulo: Mapped[str] = mapped_column(String(300), default='Conversa de IA')
    origem: Mapped[str] = mapped_column(String(40), default='reqsys', index=True)
    status: Mapped[str] = mapped_column(String(30), default='aguardando_usuario', index=True)
    correlation_id: Mapped[str] = mapped_column(String(160), index=True)

    tenant_id: Mapped[str] = mapped_column(String(120), default='default', index=True)
    area_id: Mapped[str] = mapped_column(String(120), default='default', index=True)
    requester_id: Mapped[str] = mapped_column(String(160), default='system', index=True)
    cost_center: Mapped[str] = mapped_column(String(120), default='default', index=True)

    data_classification: Mapped[str] = mapped_column(String(20), default='internal', index=True)
    classification_lock_sha256: Mapped[str] = mapped_column(String(64), index=True)
    requested_provider: Mapped[str] = mapped_column(String(30), index=True)
    authorized_provider: Mapped[str] = mapped_column(String(30), index=True)
    policy_mode: Mapped[str] = mapped_column(String(20), default='off', index=True)
    policy_decision: Mapped[str] = mapped_column(String(20), default='allowed', index=True)
    policy_reason: Mapped[str] = mapped_column(String(500))
    policy_correlation_id: Mapped[str] = mapped_column(String(160), index=True)

    teams_destino_tipo: Mapped[str] = mapped_column(String(20), default='auto')
    teams_destino_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    teams_modo: Mapped[str] = mapped_column(String(30), default='auto')
    teams_permitir_fallback: Mapped[bool] = mapped_column(default=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ultima_mensagem_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIConversationMessage(Base):
    """Mensagem persistida para continuidade, auditoria e idempotência."""

    __tablename__ = 'ai_conversation_messages'
    __table_args__ = (
        UniqueConstraint('conversation_id', 'idempotency_key', name='uq_ai_conversation_message_idempotency'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('ai_conversations.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(EncryptedText())
    source: Mapped[str] = mapped_column(String(30), default='api', index=True)
    correlation_id: Mapped[str] = mapped_column(String(160), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIUsageLedger(Base):
    """Consumo estimado e auditável por usuário/centro de custo."""

    __tablename__ = 'ai_usage_ledger'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('ai_conversations.id', ondelete='CASCADE'), index=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    requester_id: Mapped[str] = mapped_column(String(160), index=True)
    cost_center: Mapped[str] = mapped_column(String(120), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    model: Mapped[str] = mapped_column(String(160), index=True)
    correlation_id: Mapped[str] = mapped_column(String(160), index=True)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer)
    total_estimated_tokens: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
