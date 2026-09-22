from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BotConversaReferencia(Base):
    """Conversation reference do Bot Framework, capturada no conversationUpdate do Teams.

    Necessaria porque o bot so pode enviar mensagem proativa 1:1 depois de ter
    sido instalado/mencionado ao menos uma vez pelo usuario-alvo (Teams nao
    permite iniciar uma conversa do zero via Bot Framework).
    """

    __tablename__ = 'bot_conversa_referencia'
    __table_args__ = (UniqueConstraint('usuario_aad_object_id', 'channel_id', name='uq_bot_conversa_usuario_canal'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    usuario_aad_object_id: Mapped[str] = mapped_column(String(120), index=True)
    channel_id: Mapped[str] = mapped_column(String(40), default='msteams')
    service_url: Mapped[str] = mapped_column(String(500))
    conversation_id: Mapped[str] = mapped_column(String(300))
    bot_id: Mapped[str] = mapped_column(String(300), default='')
    tenant_id: Mapped[str] = mapped_column(String(120), default='')
