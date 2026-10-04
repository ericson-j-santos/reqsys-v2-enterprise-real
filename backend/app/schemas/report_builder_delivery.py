from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.paginated_report import PaginatedReportGenerateRequest


class ReportBuilderEmailRequest(BaseModel):
    report: PaginatedReportGenerateRequest
    recipients: list[EmailStr] = Field(min_length=1, max_length=20)
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=5000)
    dry_run: bool = True

    @field_validator('recipients')
    @classmethod
    def normalizar_destinatarios(cls, value: list[EmailStr]) -> list[EmailStr]:
        vistos: set[str] = set()
        resultado: list[EmailStr] = []
        for item in value:
            chave = str(item).casefold()
            if chave not in vistos:
                vistos.add(chave)
                resultado.append(item)
        if not resultado:
            raise ValueError('Ao menos um destinatário válido é obrigatório.')
        return resultado

    @field_validator('subject')
    @classmethod
    def validar_assunto(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if '\n' in value or '\r' in value:
            raise ValueError('subject deve conter somente uma linha.')
        if not value:
            raise ValueError('subject não pode ser vazio.')
        return value
