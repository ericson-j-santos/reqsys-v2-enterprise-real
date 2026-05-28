from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.envelope import ok
from app.services.gemini import (
    GeminiIndisponivel,
    classificar_urgencia,
    get_uso,
    resumir_requisito,
    sugerir_descricao,
)

router = APIRouter(prefix='/v1/ia', tags=['IA Assistente'])


class ResumoRequest(BaseModel):
    titulo: str
    descricao: str


class SugestaoDescricaoRequest(BaseModel):
    titulo: str
    area: str = ''
    sistema: str = ''


class ClassificacaoRequest(BaseModel):
    titulo: str
    descricao: str


def _handle_gemini_error(exc: GeminiIndisponivel):
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post('/resumir')
def resumir(body: ResumoRequest):
    """Gera um resumo de 2 frases para o requisito."""
    try:
        resumo = resumir_requisito(
            titulo=body.titulo,
            descricao=body.descricao,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        return ok({'resumo': resumo})
    except GeminiIndisponivel as exc:
        _handle_gemini_error(exc)


@router.post('/sugerir-descricao')
def sugerir(body: SugestaoDescricaoRequest):
    """Sugere uma descrição completa para o requisito com base no título, área e sistema."""
    try:
        descricao = sugerir_descricao(
            titulo=body.titulo,
            area=body.area,
            sistema=body.sistema,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        return ok({'descricao_sugerida': descricao})
    except GeminiIndisponivel as exc:
        _handle_gemini_error(exc)


@router.post('/classificar-urgencia')
def classificar(body: ClassificacaoRequest):
    """Sugere urgência (baixa/media/alta/critica) e justificativa para o requisito."""
    try:
        resultado = classificar_urgencia(
            titulo=body.titulo,
            descricao=body.descricao,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        return ok({'urgencia': resultado.urgencia, 'justificativa': resultado.justificativa})
    except GeminiIndisponivel as exc:
        _handle_gemini_error(exc)


@router.get('/status')
def ia_status():
    """Verifica configuração Gemini e mostra cota restante do free tier."""
    configurada = bool(settings.gemini_api_key)
    uso = get_uso()
    return ok({
        'configurada': configurada,
        'modelo': settings.gemini_model,
        'aviso': None if configurada else 'GEMINI_API_KEY não configurada no .env',
        'cota': uso,
    })
