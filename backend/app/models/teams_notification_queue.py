from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TeamsNotificationQueueItem(Base):
    """Mensagem governada do painel central de notificações Teams.

    Destino e conteúdo são persistidos apenas para permitir retentativa operacional.
    Nenhum endpoint serializa esses campos brutos; a UI recebe somente o destino
    mascarado e o hash de rastreabilidade.
    """

    __tablename__ = 'teams_notification_queue'

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    ultima_tentativa_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enviado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    origem: Mapped[str] = mapped_column(String(30), index=True)
    tipo_evento: Mapped[str] = mapped_column(String(80), index=True)
    ambiente: Mapped[str] = mapped_column(String(40), default='unknown', index=True)
    correlation_id: Mapped[str] = mapped_column(String(160), index=True)

    titulo: Mapped[str] = mapped_column(String(300), default='')
    texto: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(10), default='text')
    autor: Mapped[str] = mapped_column(String(120), default='reqsys')
    metadata_json: Mapped[str] = mapped_column(Text, default='{}')

    destino_tipo: Mapped[str] = mapped_column(String(20), default='auto')
    destino_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    destino_mascarado: Mapped[str] = mapped_column(String(200), default='Automático')
    destino_hash: Mapped[str] = mapped_column(String(64), default='', index=True)
    modo: Mapped[str] = mapped_column(String(30), default='auto')
    permitir_fallback: Mapped[bool] = mapped_column(default=True)
    dry_run: Mapped[bool] = mapped_column(default=False)

    status_evento: Mapped[str] = mapped_column(
        String(20), default='PENDENTE', index=True
    )
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    max_tentativas: Mapped[int] = mapped_column(Integer, default=3)
    canal_usado: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status_http: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    motivo_falha: Mapped[str | None] = mapped_column(Text, nullable=True)
