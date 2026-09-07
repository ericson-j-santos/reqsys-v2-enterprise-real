from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

AIProvider = Literal['openai', 'claude', 'gemini', 'groq', 'ollama']
TeamsDestinationType = Literal['auto', 'chat', 'chat_1a1', 'canal', 'webhook']
TeamsMode = Literal['auto', 'graph_delegado', 'webhook', 'graph_app_only', 'bot', 'flow_bot']


class AIConversationCreateRequest(BaseModel):
    provider: AIProvider
    model: str = Field(..., min_length=1, max_length=160)
    mensagem: str = Field(..., min_length=1, max_length=20000)
    titulo: str = Field(default='Conversa de IA', min_length=1, max_length=300)
    origem: str = Field(default='reqsys', min_length=1, max_length=40)
    idempotency_key: str | None = Field(default=None, max_length=200)
    teams_destino_tipo: TeamsDestinationType = 'auto'
    teams_destino_id: str | None = Field(default=None, max_length=500)
    teams_modo: TeamsMode = 'auto'
    teams_permitir_fallback: bool = True
    enviar_teams: bool = True

    @field_validator('model', 'mensagem', 'titulo', 'origem', 'idempotency_key', 'teams_destino_id', mode='before')
    @classmethod
    def normalizar_textos(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class AIConversationReplyRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=20000)
    idempotency_key: str | None = Field(default=None, max_length=200)
    origem: str = Field(default='teams', min_length=1, max_length=40)
    enviar_teams: bool = True

    @field_validator('mensagem', 'idempotency_key', 'origem', mode='before')
    @classmethod
    def normalizar_textos(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value
