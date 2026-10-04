from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CopilotAgentModule = Literal['demandas', 'aprovacoes', 'releases']


class CopilotStudioSolutionGenerateRequest(BaseModel):
    solution_name: str = Field(default='ReqSysLowCodeCopilot', min_length=3, max_length=80)
    display_name: str = Field(default='ReqSys Copilot Studio', min_length=3, max_length=120)
    description: str = Field(
        default=(
            'Solucao multiagente Copilot Studio do ReqSys: orquestrador + agentes '
            'especialistas com topicos e workflows Power Automate governados.'
        ),
        max_length=1000,
    )
    target_environment: str = Field(default='dev', min_length=2, max_length=40)
    owner_prefix: str = Field(default='reqsys', min_length=2, max_length=20)
    agents: list[CopilotAgentModule] = Field(
        default_factory=lambda: ['demandas', 'aprovacoes', 'releases']
    )
    include_alm_package: bool = True
    include_canvas_markdown: bool = True
    dry_run: bool = True

    @field_validator('solution_name', 'display_name', 'target_environment', 'owner_prefix')
    @classmethod
    def validar_texto_curto(cls, value: str) -> str:
        texto = value.strip()
        if not texto:
            raise ValueError('Campo obrigatorio.')
        if '\n' in texto or '\r' in texto:
            raise ValueError('Campo nao pode conter quebra de linha.')
        return texto

    @field_validator('agents')
    @classmethod
    def validar_agentes(cls, value: list[CopilotAgentModule]) -> list[CopilotAgentModule]:
        if not value:
            raise ValueError('Informe ao menos um agente especialista.')
        return list(dict.fromkeys(value))
