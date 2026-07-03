from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LowCodeModule = Literal['dataverse', 'powerapps', 'powerautomate', 'copilot', 'security']


class LowCodeSolutionGenerateRequest(BaseModel):
    solution_name: str = Field(default='ReqSysLowCode', min_length=3, max_length=80)
    display_name: str = Field(default='ReqSys Low-Code', min_length=3, max_length=120)
    description: str = Field(
        default='Versao low-code do ReqSys com Dataverse, Power Apps, Power Automate, Copilot Studio e governanca ALM.',
        max_length=1000,
    )
    target_environment: str = Field(default='dev', min_length=2, max_length=40)
    modules: list[LowCodeModule] = Field(
        default_factory=lambda: ['dataverse', 'powerapps', 'powerautomate', 'copilot', 'security']
    )
    owner_prefix: str = Field(default='reqsys', min_length=2, max_length=20)
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

    @field_validator('modules')
    @classmethod
    def validar_modulos(cls, value: list[LowCodeModule]) -> list[LowCodeModule]:
        if not value:
            raise ValueError('Informe ao menos um modulo.')
        return list(dict.fromkeys(value))

