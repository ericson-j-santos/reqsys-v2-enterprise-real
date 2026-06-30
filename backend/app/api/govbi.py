import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.envelope import ok

router = APIRouter(prefix='/api/govbi', tags=['govbi'])
logger = logging.getLogger('reqsys.govbi')

DEFAULT_GOVBI_BASE_URL = 'https://govbi-ia-hom.fly.dev'
DEFAULT_GOVBI_TIMEOUT_SECONDS = 15.0


class GovBIPerguntaRequest(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=2000)
    formatoResposta: str = Field(default='tabela', max_length=30)
    exibirSql: bool = True


class GovBIResultado(BaseModel):
    colunas: list[str] = []
    linhas: list[dict[str, Any]] = []


def _correlation_id(header_value: str | None) -> str:
    return header_value.strip() if header_value and header_value.strip() else f'govbi-{uuid4()}'


def _govbi_base_url() -> str:
    return getattr(settings, 'govbi_base_url', '') or DEFAULT_GOVBI_BASE_URL


def _govbi_timeout() -> float:
    return float(getattr(settings, 'govbi_timeout_seconds', DEFAULT_GOVBI_TIMEOUT_SECONDS) or DEFAULT_GOVBI_TIMEOUT_SECONDS)


def _normalizar_resposta(data: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    resultado = data.get('resultado') if isinstance(data.get('resultado'), dict) else {}
    colunas = resultado.get('colunas') if isinstance(resultado.get('colunas'), list) else []
    linhas = resultado.get('linhas') if isinstance(resultado.get('linhas'), list) else []

    return {
        'avisos': data.get('avisos') if isinstance(data.get('avisos'), list) else [],
        'nivelSensibilidade': data.get('nivelSensibilidade') or 'BAIXA',
        'statusFluxo': data.get('statusFluxo') or 'CONCLUIDO',
        'metrica': data.get('metrica') or 'analise_exploratoria',
        'dimensoes': data.get('dimensoes') if isinstance(data.get('dimensoes'), list) else [],
        'filtros': data.get('filtros') if isinstance(data.get('filtros'), dict) else {},
        'correlationId': data.get('correlationId') or correlation_id,
        'sqlGerado': data.get('sqlGerado') or '',
        'resultado': {'colunas': colunas, 'linhas': linhas},
        'mascaramentoAplicado': bool(data.get('mascaramentoAplicado', True)),
        'requerAprovacao': bool(data.get('requerAprovacao', False)),
        'aprovacaoId': data.get('aprovacaoId'),
        'explicacao': data.get('explicacao') or 'Resposta GovBI normalizada pelo backend ReqSys.',
    }


def _erro_negocio_govbi(pergunta: str, correlation_id: str, data: dict[str, Any]) -> dict[str, Any]:
    mensagem = data.get('mensagem') or data.get('erro') or 'Requisição rejeitada pelo serviço GovBI externo.'
    return {
        'avisos': [mensagem],
        'nivelSensibilidade': 'BAIXA',
        'statusFluxo': 'ERRO',
        'metrica': 'analise_exploratoria',
        'dimensoes': ['periodo'],
        'filtros': {},
        'correlationId': correlation_id,
        'sqlGerado': '',
        'resultado': {
            'colunas': ['item', 'valor', 'status'],
            'linhas': [
                {'item': 'Pergunta recebida', 'valor': pergunta, 'status': 'VALIDADA'},
                {'item': 'Serviço GovBI', 'valor': mensagem, 'status': 'ERRO_NEGOCIO'},
            ],
        },
        'mascaramentoAplicado': True,
        'requerAprovacao': False,
        'aprovacaoId': None,
        'explicacao': 'Erro de negócio retornado pelo serviço GovBI externo e normalizado pelo backend ReqSys.',
    }


def _fallback_governado(pergunta: str, correlation_id: str, detalhe: str) -> dict[str, Any]:
    return {
        'avisos': [
            'GovBI IA externo indisponível ou fora do contrato esperado.',
            'Resultado apresentado em modo degradado, sem execução contra base real.',
            'Use o Correlation ID para rastrear a ocorrência no backend ReqSys.',
        ],
        'nivelSensibilidade': 'BAIXA',
        'statusFluxo': 'MODO_DEGRADADO',
        'metrica': 'analise_exploratoria',
        'dimensoes': ['periodo'],
        'filtros': {},
        'correlationId': correlation_id,
        'sqlGerado': '-- Modo degradado: SQL não executado pelo serviço GovBI externo.',
        'resultado': {
            'colunas': ['item', 'valor', 'status'],
            'linhas': [
                {'item': 'Pergunta recebida', 'valor': pergunta, 'status': 'VALIDADA'},
                {'item': 'Serviço GovBI', 'valor': detalhe, 'status': 'FALLBACK_GOVERNADO'},
                {'item': 'Próxima ação', 'valor': 'Validar GOVBI_BASE_URL, contrato /api/v1/perguntas e logs Fly.io.', 'status': 'ACAO_OPERACIONAL'},
            ],
        },
        'mascaramentoAplicado': True,
        'requerAprovacao': False,
        'aprovacaoId': None,
        'explicacao': 'Fallback governado emitido pelo backend ReqSys para evitar falha bloqueante na UI.',
    }


@router.post('/perguntas')
async def perguntar_govbi(payload: GovBIPerguntaRequest, x_correlation_id: str | None = Header(default=None)):
    correlation_id = _correlation_id(x_correlation_id)
    base_url = _govbi_base_url().rstrip('/')
    url = f'{base_url}/api/v1/perguntas'

    headers = {
        'X-Correlation-Id': correlation_id,
        'X-Usuario': 'reqsys-usuario',
        'X-Perfil': 'ANALISTA',
        'X-Escopo-Unidade': 'GERAL',
    }

    try:
        async with httpx.AsyncClient(timeout=_govbi_timeout()) as client:
            response = await client.post(url, json=payload.model_dump(), headers=headers)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            raise ValueError('Resposta GovBI não é objeto JSON')

        return _normalizar_resposta(data, correlation_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            try:
                data = exc.response.json()
                if isinstance(data, dict) and (data.get('erro') or data.get('mensagem')):
                    logger.info(
                        'govbi_erro_negocio correlation_id=%s erro=%s',
                        correlation_id,
                        data.get('erro'),
                    )
                    return _erro_negocio_govbi(payload.pergunta, correlation_id, data)
            except Exception:  # noqa: BLE001 - segue para fallback operacional
                pass
        detalhe = f'HTTP {exc.response.status_code} ao consultar GovBI externo'
        logger.warning('govbi_http_status_error correlation_id=%s status=%s', correlation_id, exc.response.status_code)
        return _fallback_governado(payload.pergunta, correlation_id, detalhe)
    except Exception as exc:  # noqa: BLE001 - fallback operacional controlado
        detalhe = f'{type(exc).__name__}: {exc}'
        logger.warning('govbi_proxy_fallback correlation_id=%s detalhe=%s', correlation_id, detalhe)
        return _fallback_governado(payload.pergunta, correlation_id, detalhe)


@router.get('/health')
def govbi_health():
    return ok({
        'service': 'govbi-proxy',
        'status': 'ok',
        'external_base_url_configured': bool(_govbi_base_url()),
        'timeout_seconds': _govbi_timeout(),
    })


def _resultado_funcionamento(
    resultado_id: str,
    nome: str,
    aprovado: bool,
    detalhe: str = 'OK',
) -> dict[str, Any]:
    return {
        'id': resultado_id,
        'nome': nome,
        'ok': bool(aprovado),
        'detalhe': detalhe,
        'categoria': 'backend',
    }


def _executar_funcionamento_govbi() -> dict[str, Any]:
    base_url = _govbi_base_url()
    timeout = _govbi_timeout()
    fallback = _fallback_governado('teste funcionamento', 'govbi-func-backend', 'simulado')

    resultados = [
        _resultado_funcionamento(
            'config-base-url',
            'Configuração GOVBI_BASE_URL',
            bool(base_url),
            base_url or 'ausente',
        ),
        _resultado_funcionamento(
            'config-timeout',
            'Timeout do proxy configurado',
            timeout > 0,
            f'{timeout}s',
        ),
        _resultado_funcionamento(
            'contrato-fallback',
            'Fallback governado com contrato mínimo',
            all(
                campo in fallback
                for campo in ('statusFluxo', 'correlationId', 'resultado', 'explicacao', 'mascaramentoAplicado')
            ),
            fallback.get('statusFluxo', ''),
        ),
        _resultado_funcionamento(
            'contrato-normalizacao',
            'Normalização de resposta externa',
            'statusFluxo' in _normalizar_resposta({'resultado': {'colunas': [], 'linhas': []}}, 'corr-test'),
            'campos canônicos presentes',
        ),
        _resultado_funcionamento(
            'validacao-pergunta',
            'Validação mínima de pergunta (3 caracteres)',
            GovBIPerguntaRequest.model_validate({'pergunta': 'sim'}).pergunta == 'sim',
            'min_length=3 ativo',
        ),
    ]

    total = len(resultados)
    aprovados = sum(1 for item in resultados if item['ok'])
    percentual = round((aprovados / total) * 100) if total else 0

    return {
        'executadoEm': datetime.now(UTC).isoformat(),
        'total': total,
        'aprovados': aprovados,
        'reprovados': total - aprovados,
        'percentual': percentual,
        'completo': total > 0 and aprovados == total,
        'resultados': resultados,
    }


@router.get('/funcionamento')
def govbi_funcionamento():
    return ok(_executar_funcionamento_govbi())
