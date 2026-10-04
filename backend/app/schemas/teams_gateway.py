from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TeamsGatewayDestinoTipo = Literal['auto', 'chat', 'chat_1a1', 'canal', 'webhook']
TeamsGatewayModo = Literal['auto', 'graph_delegado', 'webhook', 'graph_app_only', 'bot', 'flow_bot']
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


class TeamsFlowBotOwnerCreate(BaseModel):
    owner_email: str = Field(..., min_length=3, max_length=200)
    webhook_url: str = Field(..., min_length=10, max_length=2000)
    prioridade: int = Field(default=100, ge=0, le=100000)
    ativo: bool = True
    observacao: str = Field(default='', max_length=500)

    @field_validator('owner_email', 'webhook_url', 'observacao', mode='before')
    @classmethod
    def _normalizar(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator('owner_email')
    @classmethod
    def _validar_email(cls, value: str) -> str:
        if '@' not in value:
            raise ValueError('owner_email invalido.')
        return value


class TeamsFlowBotOwnerUpdate(BaseModel):
    webhook_url: str | None = Field(default=None, min_length=10, max_length=2000)
    prioridade: int | None = Field(default=None, ge=0, le=100000)
    ativo: bool | None = None
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator('webhook_url', 'observacao', mode='before')
    @classmethod
    def _normalizar(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class TeamsFlowBotOwnerOut(BaseModel):
    id: int
    owner_email: str
    prioridade: int
    ativo: bool
    observacao: str
    webhook_configurado: bool = True


class TeamsFlowBotClonarFlowRequest(BaseModel):
    environment: str = Field(..., min_length=3, max_length=200)
    flow_id_origem: str = Field(..., min_length=3, max_length=200)
    nova_connection_id: str = Field(..., min_length=3, max_length=500)
    novo_display_name: str = Field(..., min_length=3, max_length=200)
    connection_reference_key: str | None = Field(default=None, max_length=200)

    @field_validator(
        'environment', 'flow_id_origem', 'nova_connection_id', 'novo_display_name', 'connection_reference_key',
        mode='before',
    )
    @classmethod
    def _normalizar(cls, value: Any) -> Any:
        if isinstance(value, str):
            texto = value.strip()
            return texto or None
        return value


class TeamsFlowBotPromoverSolutionRequest(BaseModel):
    environment_url_origem: str = Field(..., min_length=10, max_length=500)
    environment_url_destino: str = Field(..., min_length=10, max_length=500)
    solution_name: str = Field(..., min_length=2, max_length=200)
    connection_reference_logical_name: str = Field(..., min_length=2, max_length=200)
    connection_id_destino: str = Field(..., min_length=3, max_length=500)
    novo_flow_display_name: str = Field(..., min_length=3, max_length=200)
    managed: bool = False

    @field_validator(
        'environment_url_origem', 'environment_url_destino', 'solution_name',
        'connection_reference_logical_name', 'connection_id_destino', 'novo_flow_display_name',
        mode='before',
    )
    @classmethod
    def _normalizar(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value
