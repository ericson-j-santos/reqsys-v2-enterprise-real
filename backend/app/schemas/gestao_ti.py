from pydantic import BaseModel, ConfigDict, Field


class ServicoTICriar(BaseModel):
    codigo: str = Field(min_length=2, max_length=80, pattern=r'^[A-Z0-9][A-Z0-9_-]+$')
    nome: str = Field(min_length=3, max_length=200)
    descricao: str | None = Field(default=None, max_length=1000)
    criticidade: str = Field(default='media', pattern='^(baixa|media|alta|critica)$')
    responsavel_tecnico: str = Field(min_length=2, max_length=200)
    responsavel_negocio: str = Field(min_length=2, max_length=200)


class ServicoTIOut(ServicoTICriar):
    servico_id: str
    versao_catalogo: int
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


class RequisitoServicoVincular(BaseModel):
    requisito_id: int = Field(gt=0)
    servico_id: str = Field(min_length=36, max_length=36)


class RequisitoServicoOut(BaseModel):
    requisito_id: int
    requisito_codigo: str
    requisito_titulo: str
    servico_id: str
    servico_codigo: str
    servico_nome: str
    correlation_id: str
