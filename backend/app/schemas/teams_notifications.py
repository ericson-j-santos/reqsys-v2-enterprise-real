from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

NotificationOrigin = Literal['commit', 'ci', 'logs', 'hitl', 'manual', 'gateway', 'sistema', 'requisitos']
NotificationDestinationType = Literal['auto', 'chat', 'chat_1a1', 'canal', 'webhook']
NotificationMode = Literal['auto', 'graph_delegado', 'webhook', 'graph_app_only', 'bot', 'flow_bot']
NotificationContentType = Literal['text', 'html']


class TeamsNotificationEnqueueRequest(BaseModel):
    origem: NotificationOrigin = 'manual'
    tipo_evento: str = Field(default='mensagem_manual', min_length=2, max_length=80)
    ambiente: str = Field(default='unknown', min_length=2, max_length=40)
    correlation_id: str | None = Field(default=None, max_length=160)

    titulo: str = Field(..., min_length=1, max_length=300)
    texto: str = Field(..., min_length=1, max_length=20000)
    content_type: NotificationContentType = 'text'
    autor: str = Field(default='reqsys', min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    destino_tipo: NotificationDestinationType = 'auto'
    destino_id: str | None = Field(default=None, max_length=500)
    modo: NotificationMode = 'auto'
    permitir_fallback: bool = True
    dry_run: bool = False

    enviar_agora: bool = True
    max_tentativas: int = Field(default=3, ge=1, le=10)

    @field_validator(
        'tipo_evento',
        'ambiente',
        'correlation_id',
        'titulo',
        'texto',
        'autor',
        'destino_id',
        mode='before',
    )
    @classmethod
    def normalizar_textos(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value
