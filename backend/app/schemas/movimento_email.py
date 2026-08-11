from datetime import date

from pydantic import BaseModel, EmailStr


class MovimentoEmailJobRequest(BaseModel):
    data_referencia: date | None = None
    destinatarios: list[EmailStr] | None = None


class MovimentoEmailConsumirRequest(BaseModel):
    dry_run: bool = False
    lote_max: int | None = None
