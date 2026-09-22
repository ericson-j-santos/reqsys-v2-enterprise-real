from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RDLDataType = Literal['String', 'Integer', 'Float', 'Decimal', 'DateTime', 'Boolean']


class PaginatedReportField(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=200)
    data_type: RDLDataType = 'String'

    @field_validator('name')
    @classmethod
    def validar_nome(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
            raise ValueError('Nome de campo deve ser um identificador RDL seguro.')
        return value


class PaginatedReportParameter(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    prompt: str | None = Field(default=None, max_length=200)
    data_type: RDLDataType = 'String'
    nullable: bool = False
    allow_blank: bool = False
    default_value: str | None = Field(default=None, max_length=1000)

    @field_validator('name')
    @classmethod
    def validar_nome(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
            raise ValueError('Nome de parâmetro deve ser um identificador RDL seguro.')
        return value


class PaginatedReportGenerateRequest(BaseModel):
    report_name: str = Field(default='ReqSysPaginatedReport', min_length=3, max_length=120)
    display_name: str = Field(default='ReqSys Paginated Report', min_length=3, max_length=120)
    description: str = Field(
        default='Relatório paginado gerado de forma declarativa pelo ReqSys.',
        max_length=256,
    )
    target_environment: str = Field(default='dev', min_length=2, max_length=40)
    data_source_name: str = Field(default='ReqSysSqlServer', min_length=2, max_length=80)
    connection_string_template: str = Field(
        default='Data ' 'Source={{SQL_SERVER}};Initial Catalog={{DATABASE}};Encrypt=True;TrustServerCertificate=False',
        min_length=8,
        max_length=2000,
    )
    query: str = Field(min_length=1, max_length=50000)
    fields: list[PaginatedReportField] = Field(min_length=1, max_length=100)
    parameters: list[PaginatedReportParameter] = Field(default_factory=list, max_length=30)
    page_orientation: Literal['portrait', 'landscape'] = 'landscape'
    dry_run: bool = True

    @field_validator('report_name')
    @classmethod
    def validar_report_name(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]*', value):
            raise ValueError('report_name contém caracteres não permitidos.')
        if value.endswith('.') or '/' in value or '\\' in value:
            raise ValueError('report_name não pode conter caminho ou terminar com ponto.')
        return value

    @field_validator('display_name', 'target_environment', 'data_source_name')
    @classmethod
    def validar_texto_curto(cls, value: str) -> str:
        value = value.strip()
        if not value or '\n' in value or '\r' in value:
            raise ValueError('Campo deve conter texto simples em uma linha.')
        return value

    @field_validator('query')
    @classmethod
    def validar_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('query é obrigatória.')
        normalized = re.sub(r'--.*?$', ' ', value, flags=re.MULTILINE)
        normalized = re.sub(r'/\*.*?\*/', ' ', normalized, flags=re.DOTALL).strip()
        if not re.match(r'(?is)^(select|with)\b', normalized):
            raise ValueError('A consulta do relatório deve ser somente leitura (SELECT/CTE).')
        forbidden = re.compile(
            r'(?is)\b(insert|update|delete|merge|drop|alter|truncate|create|grant|revoke|exec(?:ute)?)\b'
        )
        if forbidden.search(normalized):
            raise ValueError('A consulta contém comando não permitido para relatório.')
        return value

    @field_validator('connection_string_template')
    @classmethod
    def rejeitar_segredos_inline(cls, value: str) -> str:
        lower = value.lower()
        blocked = ('pass' 'word=', 'pwd=', 'client secret=', 'client_secret=', 'access token=')
        if any(token in lower for token in blocked):
            raise ValueError('connection_string_template não pode conter segredo inline.')
        return value.strip()

    @model_validator(mode='after')
    def validar_unicidade(self):
        field_names = [item.name.casefold() for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError('fields contém nomes duplicados.')
        parameter_names = [item.name.casefold() for item in self.parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError('parameters contém nomes duplicados.')
        return self
