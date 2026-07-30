from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.teams_gateway import (
    TeamsGatewayDestinoTipo,
    TeamsGatewayMessageRequest,
)


TeamsRecipientDeliveryMode = Literal['all', 'first_success', 'channel']


class TeamsRecipientPolicyMessageRequest(TeamsGatewayMessageRequest):
    delivery_mode: TeamsRecipientDeliveryMode = 'all'


class TeamsNotificationRecipientCreate(BaseModel):
    politica: str = Field(..., min_length=2, max_length=120)
    nome: str = Field(default='', max_length=200)
    destino_id: str = Field(..., min_length=2, max_length=500)
    destino_tipo: TeamsGatewayDestinoTipo = 'chat'
    prioridade: int = Field(default=100, ge=0, le=100000)
    ativo: bool = True
    observacao: str = Field(default='', max_length=500)

    @field_validator('politica', 'nome', 'destino_id', 'observacao', mode='before')
    @classmethod
    def normalizar_texto(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator('politica')
    @classmethod
    def validar_politica(cls, value: str) -> str:
        if not all(char.isalnum() or char in '._-' for char in value):
            raise ValueError('politica aceita apenas letras, numeros, ponto, sublinhado e hifen.')
        return value.lower()


class TeamsNotificationRecipientUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=200)
    destino_id: str | None = Field(default=None, min_length=2, max_length=500)
    destino_tipo: TeamsGatewayDestinoTipo | None = None
    prioridade: int | None = Field(default=None, ge=0, le=100000)
    ativo: bool | None = None
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator('nome', 'destino_id', 'observacao', mode='before')
    @classmethod
    def normalizar_texto(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value
