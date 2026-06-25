import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from app.core.autonomous_operations import gerar_snapshot_operacao_autonoma
from app.core.config import settings
from app.core.envelope import ok
from app.core.runtime_remediation import (
    RemediationRequest,
    avaliar_remediacao,
    criar_health_snapshot_base,
)
from app.core.security import require_admin

router = APIRouter(tags=['Monitoramento Operacional'])
logger = logging.getLogger(__name__)
STARTED_AT = datetime.now(timezone.utc)
STARTED_MONOTONIC = time.monotonic()


class ItemMonitorado(BaseModel):
    tipo: str
    referencia: str
    titulo: str
    estado: str = Field(pattern='^(verde|amarelo|vermelho|bloqueado|desconhecido)$')
    severidade: str = Field(pattern='^(baixa|media|alta|critica)$')
    origem: str
    pronto_para_merge: bool = False
    bloqueante: bool = False
    detalhes: dict = Field(default_factory=dict)


class ResumoMonitoramento(BaseModel):
    estado_geral: str
    bloqueios: int
    pendencias: int
    total_itens: int


class MonitoramentoOperacional(BaseModel):
    schema_version: str = '1.0.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    resumo: ResumoMonitoramento
    itens: list[ItemMonitorado]


def classificar_estado_geral(itens: list[ItemMonitorado]) -> str:
    if not itens:
        return 'desconhecido'
    if any(item.estado == 'bloqueado' or item.bloqueante for item in itens):
        return 'bloqueado'
    if any(item.estado == 'vermelho' for item in itens):
        return 'vermelho'
    if any(item.estado in {'amarelo', 'desconhecido'} for item in itens):
        return 'amarelo'
    return 'verde'


def criar_snapshot_minimo(correlation_id: str) -> MonitoramentoOperacional:
    itens = [
        ItemMonitorado(
            tipo='frente',
            referencia='REQSYS-OPER-005',
            titulo='Implementar monitoramento operacional',
            estado='amarelo',
            severidade='media',
            origem='issue-46',
            detalhes={'motivo': 'primeira fatia funcional em validacao'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-001',
            titulo='GovBI IA',
            estado='vermelho',
            severidade='alta',
            origem='issue-30',
            detalhes={'motivo': 'consulta operacional ainda pendente'},
        ),
        ItemMonitorado(
            tipo='frontend',
            referencia='REQSYS-OPER-002',
            titulo='Dashboard para Analitico filtrado',
            estado='amarelo',
            severidade='media',
            origem='issue-31',
            detalhes={'motivo': 'deep link e filtros ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='integracao',
            referencia='REQSYS-OPER-003',
            titulo='Planner via Low Code e API',
            estado='amarelo',
            severidade='alta',
            origem='issue-32',
            detalhes={'motivo': 'contrato e idempotencia ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='pipeline',
            referencia='REQSYS-OPER-004',
            titulo='Pipeline operacional e CI',
            estado='amarelo',
            severidade='critica',
            origem='issue-33',
            detalhes={'motivo': 'evidencias automatizadas ainda pendentes'},
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='production-gates',
            titulo='Gates obrigatorios de producao',
            estado='verde',
            severidade='critica',
            origem='reqsys',
            detalhes={'validacao': 'configuracoes inseguras bloqueiam producao'},
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-1',
            titulo='Autonomous Operations Platform - maturidade e politicas governadas',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            detalhes={
                'motivo': 'maturity score e policies implementadas; execucao destrutiva permanece bloqueada por governanca',
                'endpoint': '/operacao-autonoma/maturidade',
            },
        ),
        ItemMonitorado(
            tipo='aop',
            referencia='AOP-P0-2',
            titulo='Runtime Health Validator e Executor Governado de Remediacao',
            estado='amarelo',
            severidade='critica',
            origem='incremento-operacao-autonoma',
            detalhes={
                'motivo': 'health validator e executor dry-run implementados; acoes destrutivas seguem bloqueadas por politica',
                'endpoints': ['/operacao-autonoma/runtime-health', '/operacao-autonoma/remediacoes/avaliar'],
            },
        ),
    ]
    estado_geral = classificar_estado_geral(itens)
    return MonitoramentoOperacional(
        correlation_id=correlation_id,
        coletado_em=datetime.now(timezone.utc).isoformat(),
        ambiente=settings.normalized_environment,
        resumo=ResumoMonitoramento(
            estado_geral=estado_geral,
            bloqueios=sum(1 for item in itens if item.estado == 'bloqueado' or item.bloqueante),
            pendencias=sum(1 for item in itens if item.estado in {'amarelo', 'vermelho', 'desconhecido'}),
            total_itens=len(itens),
        ),
        itens=itens,
    )


def _resolver_correlation_id(x_correlation_id: str | None, x_request_id: str | None) -> str:
    correlation_id = x_correlation_id or x_request_id or str(uuid4())
    logger.info('monitoramento_operacional_correlation_id_resolvido', extra={'correlation_id': correlation_id})
    return correlation_id


def _runtime_status(estado_geral: str) -> str:
    if estado_geral in {'bloqueado', 'vermelho'}:
        return 'degraded'
    if estado_geral in {'amarelo', 'desconhecido'}:
        return 'attention'
    return 'healthy'


def _runtime_risk_score(snapshot: MonitoramentoOperacional) -> int:
    if snapshot.resumo.total_itens == 0:
        return 50
    severidade_peso = {'baixa': 5, 'media': 10, 'alta': 18, 'critica': 25}
    estado_peso = {'verde': 0, 'amarelo': 8, 'vermelho': 18, 'bloqueado': 30, 'desconhecido': 12}
    bruto = sum(
        estado_peso[item.estado] + (severidade_peso[item.severidade] if item.estado != 'verde' else 0)
        for item in snapshot.itens
    )
    normalizado = min(100, round(bruto / max(1, snapshot.resumo.total_itens)))
    return normalizado


def _criar_runtime_observability_snapshot(correlation_id: str) -> dict:
    snapshot = criar_snapshot_minimo(correlation_id)
    health = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    uptime_seconds = max(0, round(time.monotonic() - STARTED_MONOTONIC, 3))
    risk_score = _runtime_risk_score(snapshot)
    status = _runtime_status(snapshot.resumo.estado_geral)
    return {
        'schema_version': '1.0.0',
        'correlation_id': correlation_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'service': 'reqsys-api',
        'environment': settings.normalized_environment,
        'version': settings.app_version,
        'status': status,
        'uptime_seconds': uptime_seconds,
        'started_at': STARTED_AT.isoformat(),
        'risk_score': risk_score,
        'runtime_health': health.model_dump(),
        'operational_summary': snapshot.resumo.model_dump(),
        'critical_counts': {
            'blocked_items': snapshot.resumo.bloqueios,
            'pending_items': snapshot.resumo.pendencias,
            'total_items': snapshot.resumo.total_itens,
        },
        'evidence': {
            'source': 'runtime_operational_observability_v1',
            'no_secrets': True,
            'no_pii': True,
            'deploy_gate_relaxed': False,
        },
    }


def _metric_line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        labels_text = ','.join(f'{key}="{value}"' for key, value in sorted(labels.items()))
        return f'{name}{{{labels_text}}} {value}'
    return f'{name} {value}'


@router.get('/monitoramento-operacional')
def obter_monitoramento_operacional(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = criar_snapshot_minimo(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)


@router.get('/api/runtime/health')
def obter_api_runtime_health(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    return ok(_criar_runtime_observability_snapshot(correlation_id), correlation_id)


@router.get('/api/runtime/readiness')
def obter_api_runtime_readiness(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    ready = snapshot['status'] in {'healthy', 'attention', 'degraded'}
    return ok({'ready': ready, **snapshot}, correlation_id)


@router.get('/api/runtime/liveness')
def obter_api_runtime_liveness(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    return ok(
        {
            'alive': True,
            'service': 'reqsys-api',
            'environment': settings.normalized_environment,
            'version': settings.app_version,
            'uptime_seconds': max(0, round(time.monotonic() - STARTED_MONOTONIC, 3)),
        },
        correlation_id,
    )


@router.get('/api/runtime/metrics')
def obter_api_runtime_metrics(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    labels = {'environment': snapshot['environment'], 'service': snapshot['service']}
    lines = [
        '# HELP reqsys_runtime_up Runtime liveness status.',
        '# TYPE reqsys_runtime_up gauge',
        _metric_line('reqsys_runtime_up', 1, labels),
        '# HELP reqsys_runtime_risk_score Runtime risk score from 0 to 100.',
        '# TYPE reqsys_runtime_risk_score gauge',
        _metric_line('reqsys_runtime_risk_score', snapshot['risk_score'], labels),
        '# HELP reqsys_runtime_pending_items Pending operational items.',
        '# TYPE reqsys_runtime_pending_items gauge',
        _metric_line('reqsys_runtime_pending_items', snapshot['critical_counts']['pending_items'], labels),
        '# HELP reqsys_runtime_blocked_items Blocked operational items.',
        '# TYPE reqsys_runtime_blocked_items gauge',
        _metric_line('reqsys_runtime_blocked_items', snapshot['critical_counts']['blocked_items'], labels),
        '# HELP reqsys_runtime_uptime_seconds Runtime uptime in seconds.',
        '# TYPE reqsys_runtime_uptime_seconds counter',
        _metric_line('reqsys_runtime_uptime_seconds', snapshot['uptime_seconds'], labels),
    ]
    return Response('\n'.join(lines) + '\n', media_type='text/plain; version=0.0.4; charset=utf-8')


@router.get('/operacao-autonoma/maturidade')
def obter_maturidade_operacao_autonoma(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = gerar_snapshot_operacao_autonoma(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)


@router.get('/operacao-autonoma/runtime-health')
def obter_runtime_health(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    return ok(snapshot.model_dump(), correlation_id)


@router.post('/operacao-autonoma/remediacoes/avaliar', dependencies=[Depends(require_admin)])
def avaliar_remediacao_governada(
    payload: RemediationRequest,
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    health_snapshot = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    decisao = avaliar_remediacao(payload, health_snapshot, correlation_id)
    return ok(decisao.model_dump(), correlation_id)
