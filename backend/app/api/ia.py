from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.envelope import ok
from app.services.gemini import (
    GeminiIndisponivel,
    classificar_urgencia,
    get_uso,
    get_uso_groq,
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


def _handle_ia_error(exc: GeminiIndisponivel):
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


def _groq_params() -> dict:
    return {'groq_key': settings.groq_api_key, 'groq_model': settings.groq_model}


@router.post('/resumir')
def resumir(body: ResumoRequest):
    """Gera um resumo de 2 frases para o requisito. Fallback automático Gemini → Groq."""
    try:
        resumo, provedor = resumir_requisito(
            titulo=body.titulo,
            descricao=body.descricao,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            **_groq_params(),
        )
        return ok({'resumo': resumo, 'provedor': provedor})
    except GeminiIndisponivel as exc:
        _handle_ia_error(exc)


@router.post('/sugerir-descricao')
def sugerir(body: SugestaoDescricaoRequest):
    """Sugere descrição completa para o requisito. Fallback automático Gemini → Groq."""
    try:
        descricao, provedor = sugerir_descricao(
            titulo=body.titulo,
            area=body.area,
            sistema=body.sistema,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            **_groq_params(),
        )
        return ok({'descricao_sugerida': descricao, 'provedor': provedor})
    except GeminiIndisponivel as exc:
        _handle_ia_error(exc)


@router.post('/classificar-urgencia')
def classificar(body: ClassificacaoRequest):
    """Classifica urgência do requisito. Fallback automático Gemini → Groq."""
    try:
        resultado, provedor = classificar_urgencia(
            titulo=body.titulo,
            descricao=body.descricao,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            **_groq_params(),
        )
        return ok({'urgencia': resultado.urgencia, 'justificativa': resultado.justificativa, 'provedor': provedor})
    except GeminiIndisponivel as exc:
        _handle_ia_error(exc)


@router.get('/status')
def ia_status():
    """Verifica configuração e cota de ambos os providers (Gemini + Groq)."""
    gemini_ok = bool(settings.gemini_api_key)
    groq_ok = bool(settings.groq_api_key)
    fallback_ativo = gemini_ok and groq_ok

    avisos = []
    if not gemini_ok:
        avisos.append('GEMINI_API_KEY não configurada no .env')
    if not groq_ok:
        avisos.append('GROQ_API_KEY não configurada — fallback desativado. Obtenha em console.groq.com (grátis)')

    return ok({
        # campos de compatibilidade (Gemini é o primary)
        'configurada': gemini_ok,
        'modelo': settings.gemini_model,
        'cota': get_uso(),
        'aviso': avisos[0] if avisos else None,
        # informações detalhadas dos dois providers
        'provedores': {
            'gemini': {
                'configurado': gemini_ok,
                'modelo': settings.gemini_model,
                'cota': get_uso(),
            },
            'groq': {
                'configurado': groq_ok,
                'modelo': settings.groq_model,
                'cota': get_uso_groq(),
            },
        },
        'fallback_ativo': fallback_ativo,
        'avisos': avisos,
    })
