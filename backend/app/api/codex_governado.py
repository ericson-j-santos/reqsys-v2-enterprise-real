from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.core.security import get_current_user
from app.services.codex_governado import analisar_governado

router = APIRouter(prefix='/v1/codex', tags=['Codex Governado'])


class CodexAnalyzeRequest(BaseModel):
    provider: Literal['mock', 'ollama', 'openai', 'claude'] = 'mock'
    contexto: str = Field(min_length=1, max_length=12000)
    entrada: str = Field(min_length=1, max_length=30000)
    correlation_id: str | None = Field(default=None, max_length=120)
    publicar_no_reqsys: bool = False


@router.post('/analyze')
def analyze(body: CodexAnalyzeRequest, request: Request, user: dict = Depends(get_current_user)):
    resultado = analisar_governado(
        provider=body.provider,
        contexto=body.contexto,
        entrada=body.entrada,
        usuario=user,
        correlation_id=body.correlation_id or request.headers.get('X-Correlation-Id'),
        publicar_no_reqsys=body.publicar_no_reqsys,
    )
    if resultado.get('bloqueado') and resultado.get('motivo') == 'rate_limit':
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=resultado,
            headers={'Retry-After': str(resultado.get('retry_after_seconds', 60))},
        )
    if resultado.get('bloqueado'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resultado)
    return ok(resultado)


@router.get('/status')
def status_codex(user: dict = Depends(get_current_user)):
    return ok({
        'servico': 'codex-governado',
        'autenticado': True,
        'usuario': user.get('sub'),
        'providers': ['mock', 'ollama', 'openai', 'claude'],
        'guard_rails': ['jwt', 'rate_limit', 'auditoria', 'bloqueio_conteudo_sensivel', 'correlation_id'],
    })
