import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.envelope import ok
from app.core.security import get_current_user

router = APIRouter(prefix='/api/govbi', tags=['GovBI'])
logger = logging.getLogger('reqsys.govbi')


class GovBIPerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=1, max_length=4000)
    formatoResposta: str = Field(default='tabela', max_length=40)
    exibirSql: bool = True


class GovBIProxyStatus(BaseModel):
    status: str
    modo: str
    provider_url_configurado: bool
    timeout_ms: int


def _correlation_id(request: Request) -> str:
    return request.headers.get('X-Correlation-Id') or str(uuid4())


def _govbi_base_url() -> str:
    return (settings.govbi_base_url or 'https://govbi-ia-hom.fly.dev').rstrip('/')


def _normalizar_resposta(data: dict, pergunta: str, correlation_id: str) -> dict:
    resultado = data.get('resultado') if isinstance(data.get('resultado'), dict) else {}
    colunas = resultado.get('colunas') if isinstance(resultado.get('colunas'), list) else []
    linhas = resultado.get('linhas') if isinstance(resultado.get('linhas'), list) else []

    return {
        'avisos': data.get('avisos') if isinstance(data.get('avisos'), list) else [],
        'nivelSensibilidade': data.get('nivelSensibilidade') or 'BAIXA',
        'statusFluxo': data.get('statusFluxo') or 'CONCLUIDO',
        'metrica': data.get('metrica') or 'analise_exploratoria',
        'dimensoes': data.get('dimensoes') if isinstance(data.get('dimensoes'), list) else ['periodo'],
        'filtros': data.get('filtros') if isinstance(data.get('filtros'), dict) else {},
        'correlationId': data.get('correlationId') or correlation_id,
        'sqlGerado': data.get('sqlGerado') or '',
        'resultado': {'colunas': colunas, 'linhas': linhas},
        'mascaramentoAplicado': bool(data.get('mascaramentoAplicado')),
        'requerAprovacao': bool(data.get('requerAprovacao')),
        'aprovacaoId': data.get('aprovacaoId'),
        'explicacao': data.get('explicacao') or 'Resposta normalizada pelo proxy governado ReqSys GovBI.',
        'origem': 'govbi_externo',
        'perguntaOriginal': pergunta,
    }


def _fallback_governado(pergunta: str, detalhe: str, correlation_id: str) -> dict:
    return {
        'avisos': [
            'GovBI externo indisponível, sem resposta ou fora do contrato esperado.',
            'Resultado gerado em modo degradado pelo backend ReqSys, sem executar consulta em base real.',
            'Use o Correlation ID para rastrear a ocorrência nos logs e validar o provider externo.',
        ],
        'nivelSensibilidade': 'BAIXA',
        'statusFluxo': 'MODO_DEGRADADO',
        'metrica': 'analise_exploratoria',
        'dimensoes': ['periodo'],
        'filtros': {},
        'correlationId': correlation_id,
        'sqlGerado': (
            '-- SQL ilustrativo governado; não executado contra base real\n'
            'SELECT periodo, COUNT(*) AS analise_exploratoria\n'
            'FROM fonte_governada\n'
            'WHERE 1 = 1\n'
            'GROUP BY periodo;'
        ),
        'resultado': {
            'colunas': ['item', 'valor', 'status'],
            'linhas': [
                {'item': 'Pergunta recebida', 'valor': pergunta, 'status': 'VALIDADA_PELO_BACKEND'},
                {'item': 'GovBI externo', 'valor': detalhe, 'status': 'INDISPONIVEL_OU_FORA_DO_CONTRATO'},
                {'item': 'Próxima ação', 'valor': 'Validar health, CORS, timeout e contrato de /api/v1/perguntas no provider.', 'status': 'ACAO_OPERACIONAL'},
            ],
        },
        'mascaramentoAplicado': True,
        'requerAprovacao': False,
        'aprovacaoId': None,
        'explicacao': 'Fallback governado centralizado no backend ReqSys GovBI.',
        'origem': 'fallback_backend_reqsys',
        'perguntaOriginal': pergunta,
    }


@router.get('/status')
def status_govbi(user: dict = Depends(get_current_user)):
    return ok(
        GovBIProxyStatus(
            status='ok',
            modo='proxy_governado',
            provider_url_configurado=bool(settings.govbi_base_url.strip()),
            timeout_ms=settings.govbi_timeout_ms,
        ).model_dump(),
        meta={'usuario': user.get('sub')},
    )


@router.post('/perguntas')
async def perguntar_govbi(body: GovBIPerguntaRequest, request: Request, user: dict = Depends(get_current_user)):
    correlation_id = _correlation_id(request)
    payload = {
        'pergunta': body.pergunta.strip(),
        'formatoResposta': body.formatoResposta,
        'exibirSql': body.exibirSql,
    }
    headers = {
        'X-Correlation-Id': correlation_id,
        'X-Usuario': str(user.get('sub') or user.get('email') or 'reqsys-usuario'),
        'X-Perfil': str(user.get('papel') or 'ANALISTA').upper(),
        'X-Escopo-Unidade': 'GERAL',
    }

    url = f'{_govbi_base_url()}/api/v1/perguntas'
    timeout = max(settings.govbi_timeout_ms, 1000) / 1000

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError('payload GovBI externo não é objeto JSON')
        resultado = _normalizar_resposta(data, body.pergunta, correlation_id)
        logger.info('govbi_proxy_success correlation_id=%s usuario=%s', correlation_id, user.get('sub'))
        return ok(resultado, correlation_id=correlation_id, meta={'origem': 'govbi_externo'})
    except Exception as exc:  # noqa: BLE001 - fallback governado não deve vazar falha externa para o front
        detalhe = f'{type(exc).__name__}: {exc}'
        logger.warning('govbi_proxy_fallback correlation_id=%s detalhe=%s', correlation_id, detalhe)
        resultado = _fallback_governado(body.pergunta, detalhe, correlation_id)
        return ok(resultado, correlation_id=correlation_id, meta={'origem': 'fallback_backend_reqsys'})
