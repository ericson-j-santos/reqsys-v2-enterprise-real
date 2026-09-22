from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AgentTarget = Literal['copilot_studio']
AgentPackageType = Literal['software_lifecycle_orchestrator']
AgentProvisionMode = Literal['dry_run', 'webhook', 'dataverse_import']


class AgentGenerateRequest(BaseModel):
    name: str = Field(default='Orquestrador de Software', min_length=3, max_length=120)
    package_type: AgentPackageType = 'software_lifecycle_orchestrator'
    target: AgentTarget = 'copilot_studio'
    language: str = Field(default='pt-BR', min_length=2, max_length=12)
    include_specialists: bool = True
    include_playbook: bool = True
    include_zip_base64: bool = True

    @field_validator('name', 'language')
    @classmethod
    def validar_texto_curto(cls, value: str) -> str:
        texto = value.strip()
        if not texto:
            raise ValueError('Campo obrigatorio.')
        if '\n' in texto or '\r' in texto:
            raise ValueError('Campo nao pode conter quebra de linha.')
        return texto


class AgentGeneratedFile(BaseModel):
    path: str
    content: str


class AgentGenerateResponse(BaseModel):
    package_name: str
    target: AgentTarget
    language: str
    files: list[AgentGeneratedFile]
    zip_filename: str
    zip_base64: str | None = None
    total_files: int


class AgentProvisionRequest(AgentGenerateRequest):
    mode: AgentProvisionMode = 'dry_run'
    environment_url: str | None = None
    solution_zip_base64: str | None = None
    overwrite_unmanaged_customizations: bool = True
    publish_workflows: bool = True

    @field_validator('environment_url')
    @classmethod
    def validar_environment_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        texto = value.strip()
        if not texto:
            return None
        if not texto.startswith('https://'):
            raise ValueError('environment_url deve comecar com https://.')
        return texto.rstrip('/') + '/'


class AgentProvisionResponse(BaseModel):
    configured: bool
    provisioned: bool
    mode: AgentProvisionMode
    target: AgentTarget
    package_name: str
    message: str
    details: dict[str, Any] = {}
