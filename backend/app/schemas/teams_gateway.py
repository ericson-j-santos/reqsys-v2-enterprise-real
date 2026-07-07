from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TeamsGatewayDestinoTipo = Literal['auto', 'chat', 'chat_1a1', 'canal', 'webhook']
TeamsGatewayModo = Literal['auto', 'graph_delegado', 'webhook', 'graph_app_only', 'bot']
TeamsGatewayContentType = Literal['text', 'html']


class TeamsGatewayMessageRequest(BaseModel):
    destino_tipo: TeamsGatewayDestinoTipo = 'auto'
    modo: TeamsGatewayModo = 'auto'
    destino_id: str | None = Field(default=None, max_length=500)
    texto: str = Field(..., min_length=1, max_length=20000)
    content_type: TeamsGatewayContentType = 'text'
    usuario_access_token: str | None = Field(default=None, max_length=12000)
    webhook_url: str | None = Field(default=None, max_length=4000)
    usuario_a_aad_object_id: str | None = Field(default=None, max_length=120)
    usuario_b_aad_object_id: str | None = Field(default=None, max_length=120)
    autor: str = Field(default='reqsys', max_length=120)
    permitir_fallback: bool = True
    dry_run: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        'destino_id',
        'usuario_access_token',
        'webhook_url',
        'usuario_a_aad_object_id',
        'usuario_b_aad_object_id',
        'autor',
        mode='before',
    )
    @classmethod
    def normalizar_texto_opcional(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            texto = value.strip()
            return texto or None
        return value

    @field_validator('texto')
    @classmethod
    def validar_texto(cls, value: str) -> str:
        texto = value.strip()
        if not texto:
            raise ValueError('texto e obrigatorio.')
        return texto


class TeamsGatewayRouteStatus(BaseModel):
    canal: str
    disponivel: bool
    recomendado_para: list[str] = Field(default_factory=list)
    requer_usuario_logado: bool = False
    campos_faltantes: list[str] = Field(default_factory=list)
    observacao: str = ''


class TeamsGatewayMessageResult(BaseModel):
    entregue: bool
    canal_usado: str | None = None
    destino_tipo: str
    correlation_id: str
    dry_run: bool = False
    fallback_usado: bool = False
    message_id: str | None = None
    chat_id: str | None = None
    status_code: int | None = None
    erro: str | None = None
    motivo: str | None = None
    provider_response: dict[str, Any] = Field(default_factory=dict)
