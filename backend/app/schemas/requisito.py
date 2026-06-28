from pydantic import BaseModel, ConfigDict, Field


class RequisitoCriar(BaseModel):
    titulo: str = Field(min_length=5, max_length=200)
    descricao: str = Field(min_length=20)
    urgencia: str = 'media'
    area: str
    sistema: str
    solicitante: str
    impacto_regulatorio: bool = False


class RequisitoOut(RequisitoCriar):
    id: int
    codigo: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class RequisitoPowerAutomateCriar(BaseModel):
    schema_version: str = Field(default='1.0.0', pattern=r'^\d+\.\d+\.\d+$')
    titulo: str = Field(min_length=5, max_length=200)
    descricao: str = Field(min_length=20)
    tipo: str = Field(default='funcional', pattern='^(funcional|nao_funcional|regra_negocio|restricao)$')
    prioridade: str = Field(default='media', pattern='^(baixa|media|alta|critica)$')
    area: str = Field(default='negocio', min_length=2, max_length=80)
    sistema: str = Field(default='reqsys', min_length=2, max_length=80)
    solicitante: str = Field(default='power_automate', min_length=2, max_length=120)
    impacto_regulatorio: bool = False


class RequisitoPowerAutomateOut(BaseModel):
    schema_version: str = '1.0.0'
    id: int
    codigo: str
    titulo: str
    descricao: str
    tipo: str = 'funcional'
    prioridade: str
    status: str
    area: str
    sistema: str
    solicitante: str
    impacto_regulatorio: bool

    model_config = ConfigDict(from_attributes=True)
