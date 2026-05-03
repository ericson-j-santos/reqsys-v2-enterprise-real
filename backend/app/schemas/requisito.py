from pydantic import BaseModel, Field

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
    class Config:
        from_attributes = True
