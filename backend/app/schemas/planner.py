from __future__ import annotations

from pydantic import BaseModel, Field


class PlannerTaskIn(BaseModel):
    titulo: str
    responsavel: str = ''
    data_vencimento: str = ''
    bucket: str = ''
    prioridade: str = ''
    descricao: str = ''


class PlannerPublishRequest(BaseModel):
    tarefas: list[PlannerTaskIn]
    autor: str = ''


class PlannerWebhookConfigRequest(BaseModel):
    webhook_url: str = Field(..., min_length=10)
    webhook_key: str = ''


class PlannerDiscoveryRequest(BaseModel):
    instance_url: str = Field(default='https://orga258f260.crm2.dynamics.com')
    filtro: str = 'Planner'
