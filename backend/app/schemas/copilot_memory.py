from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


OrigemMemoria = Literal['planner', 'excel', 'reqsys', 'copilot', 'pesquisa']


class CopilotMemoryItemRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    memory_id: str | None = Field(default=None, max_length=64, alias='memoryId')
    planner_task_id: str | None = Field(default=None, max_length=200, alias='plannerTaskId')

    assunto: str | None = Field(default=None, max_length=500)
    contexto: str | None = Field(default=None, max_length=12000)
    estado_atual: str | None = Field(default=None, max_length=12000, alias='estadoAtual')
    decisao: str | None = Field(default=None, max_length=12000)
    pendencia: str | None = Field(default=None, max_length=12000)
    proximo_passo: str | None = Field(default=None, max_length=12000, alias='proximoPasso')
    fonte_url: str | None = Field(default=None, max_length=4000, alias='fonteUrl')
    data_fonte: str | None = Field(default=None, max_length=40, alias='dataFonte')
    validade: str | None = Field(default=None, max_length=30)

    planner_titulo: str | None = Field(default=None, max_length=500, alias='plannerTitulo')
    planner_status: str | None = Field(default=None, max_length=50, alias='plannerStatus')
    planner_percentual: int | None = Field(default=None, ge=0, le=100, alias='plannerPercentual')
    planner_prazo: str | None = Field(default=None, max_length=40, alias='plannerPrazo')

    origem: OrigemMemoria = 'reqsys'
    atualizar_planner: bool = Field(default=False, alias='atualizarPlanner')

    @model_validator(mode='after')
    def validar_identificador(self):
        if not (self.memory_id or self.planner_task_id):
            raise ValueError('memoryId ou plannerTaskId é obrigatório')
        if self.origem == 'planner' and not self.planner_task_id:
            raise ValueError('plannerTaskId é obrigatório quando origem=planner')
        if self.atualizar_planner and not self.planner_task_id:
            raise ValueError('plannerTaskId é obrigatório quando atualizarPlanner=true')
        return self


class CopilotMemoryBatchSyncRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[CopilotMemoryItemRequest] = Field(..., min_length=1, max_length=500)
    correlation_id: str | None = Field(default=None, max_length=80, alias='correlationId')


class PlannerSyncAckRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sucesso: bool
    planner_task_id: str | None = Field(default=None, max_length=200, alias='plannerTaskId')
    erro: str | None = Field(default=None, max_length=500)
