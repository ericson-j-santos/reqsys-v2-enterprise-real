import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Response

from app.core.autonomous_operations import gerar_snapshot_operacao_autonoma
from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.feature_metrics import REGISTRY
from app.core.runtime_analytics import (
    build_correlation_report,
    build_observability_report,
    build_runtime_topology,
)
from app.core.runtime_remediation import (
    RemediationRequest,
    avaliar_remediacao,
    criar_health_snapshot_base,
)
from app.core.security import require_admin
from app.schemas.monitoramento_operacional import MonitoramentoOperacional
from app.services.continuous_trilha_d_monitoring_history_index import (
    carregar_continuous_trilha_d_monitoring_history_index,
    mapear_cards_continuous_monitoring_history,
    mapear_secao_continuous_monitoring_history,
)
from app.services.merge_readiness_history_index import (
    carregar_merge_readiness_history_index,
    mapear_cards_merge_readiness_history,
    mapear_secao_merge_readiness_history,
)
from app.services.continuous_trilha_d_monitoring_index import (
    carregar_continuous_trilha_d_monitoring_index,
    mapear_cards_continuous_monitoring,
    mapear_secao_continuous_monitoring,
)
from app.services.governance_evidence_index import (
    carregar_governance_evidence_index,
    mapear_cards_governance,
    mapear_secao_governance,
)
from app.services.monitoramento_snapshot import criar_snapshot_operacional
from app.services.operational_mesh_signal import (
    carregar_cross_runtime_analytics_report,
    carregar_operational_mesh_signal,
    mapear_cards_operational_mesh,
    mapear_secao_operational_mesh,
    montar_payload_operational_mesh,
)
from app.services.trilha_d_history_index import (
    carregar_trilha_d_history_index,
    mapear_cards_trilha_d,
    mapear_secao_trilha_d,
)

router = APIRouter(tags=['Monitoramento Operacional'])
logger = logging.getLogger(__name__)
STARTED_AT = datetime.now(timezone.utc)
STARTED_MONOTONIC = time.monotonic()


def criar_snapshot_minimo(correlation_id: str) -> MonitoramentoOperacional:
    """Alias legado — delega ao snapshot operacional dinâmico."""
    return criar_snapshot_operacional(correlation_id)


def _resolver_correlation_id(x_correlation_id: str | None, x_request_id: str | None) -> str:
    correlation_id = resolver_correlation_id(x_correlation_id, x_request_id)
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


def _deploy_gate_relaxed() -> bool:
    """Fora de produção, pendências operacionais (OTel, auditoria, etc.) não bloqueiam readiness."""
    return not settings.is_production


def _runtime_ready(snapshot: dict) -> bool:
    if snapshot['critical_counts']['blocked_items'] > 0:
        return False
    if snapshot['evidence'].get('deploy_gate_relaxed'):
        return True
    return snapshot['status'] in {'healthy', 'attention'}


def _runtime_readiness_reason(snapshot: dict) -> str:
    if snapshot['critical_counts']['blocked_items'] > 0:
        return 'blocked_items_detected'
    if snapshot['evidence'].get('deploy_gate_relaxed'):
        return 'runtime_healthy'
    if snapshot['status'] == 'degraded':
        return 'runtime_degraded'
    if snapshot['status'] == 'attention':
        return 'runtime_requires_attention'
    return 'runtime_healthy'


def _criar_runtime_observability_snapshot(correlation_id: str) -> dict:
    snapshot = criar_snapshot_minimo(correlation_id)
    health = criar_health_snapshot_base(correlation_id, settings.normalized_environment)
    uptime_seconds = max(0, round(time.monotonic() - STARTED_MONOTONIC, 3))
    risk_score = _runtime_risk_score(snapshot)
    raw_status = _runtime_status(snapshot.resumo.estado_geral)
    deploy_gate_relaxed = _deploy_gate_relaxed()
    critical_counts = {
        'blocked_items': snapshot.resumo.bloqueios,
        'pending_items': snapshot.resumo.pendencias,
        'total_items': snapshot.resumo.total_itens,
    }
    status = 'healthy' if deploy_gate_relaxed and critical_counts['blocked_items'] == 0 else raw_status
    return {
        'schema_version': '1.0.0',
        'correlation_id': correlation_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'service': 'reqsys-api',
        'environment': settings.normalized_environment,
        'version': settings.app_version,
        'status': status,
        'status_raw': raw_status,
        'uptime_seconds': uptime_seconds,
        'started_at': STARTED_AT.isoformat(),
        'risk_score': risk_score,
        'runtime_health': health.model_dump(),
        'operational_summary': snapshot.resumo.model_dump(),
        'critical_counts': critical_counts,
        'evidence': {
            'source': 'runtime_operational_observability_v1',
            'no_secrets': True,
            'no_pii': True,
            'deploy_gate_relaxed': deploy_gate_relaxed,
            'deploy_gate_policy': (
                'non_production_pending_items_non_blocking'
                if deploy_gate_relaxed
                else 'strict_production_gate'
            ),
        },
    }


def _spa_drilldown(path: str, query: dict | None = None) -> dict:
    return {'path': path, 'query': query or {}}


def _criar_runtime_dashboard_schema(snapshot: dict) -> dict:
    topology = build_runtime_topology(snapshot, [snapshot], [], [])
    correlation_report = build_correlation_report(snapshot, [snapshot], [], [])
    observability_report = build_observability_report(snapshot, {'failure_rate': 0, 'availability_score': 100}, topology, correlation_report)
    governance_index = carregar_governance_evidence_index()
    governance_cards = mapear_cards_governance(governance_index)
    governance_section = mapear_secao_governance(governance_index)
    trilha_d_index = carregar_trilha_d_history_index()
    trilha_d_cards = mapear_cards_trilha_d(trilha_d_index)
    trilha_d_section = mapear_secao_trilha_d(trilha_d_index)
    continuous_monitoring_index = carregar_continuous_trilha_d_monitoring_index()
    continuous_monitoring_cards = mapear_cards_continuous_monitoring(continuous_monitoring_index)
    continuous_monitoring_section = mapear_secao_continuous_monitoring(continuous_monitoring_index)
    continuous_monitoring_history_index = carregar_continuous_trilha_d_monitoring_history_index()
    continuous_monitoring_history_cards = mapear_cards_continuous_monitoring_history(
        continuous_monitoring_history_index
    )
    continuous_monitoring_history_section = mapear_secao_continuous_monitoring_history(
        continuous_monitoring_history_index
    )
    merge_readiness_history_index = carregar_merge_readiness_history_index()
    merge_readiness_history_cards = mapear_cards_merge_readiness_history(merge_readiness_history_index)
    merge_readiness_history_section = mapear_secao_merge_readiness_history(merge_readiness_history_index)
    mesh_signal = carregar_operational_mesh_signal()
    mesh_cards = mapear_cards_operational_mesh(mesh_signal)
    mesh_section = mapear_secao_operational_mesh(mesh_signal)
    cross_runtime = carregar_cross_runtime_analytics_report()
    return {
        'schema_version': '1.4.0',
        'title': 'ReqSys Runtime Operational Dashboard',
        'description': 'Schema-driven dashboard para runtime publico, health, readiness e metricas operacionais.',
        'generated_at': snapshot['generated_at'],
        'correlation_id': snapshot['correlation_id'],
        'layout': {'type': 'grid', 'columns': 4, 'responsive': True},
        'correlation_analytics': correlation_report,
        'runtime_topology': topology,
        'observability_readiness': observability_report,
        'artifacts': {
            'runtime-correlation-report.json': '/api/runtime/analytics',
            'runtime-observability-report.json': '/api/runtime/analytics',
            'unified-operational-signal.json': '/api/runtime/operational-mesh',
            'github-runtime-analytics.json': '/api/runtime/analytics',
        },
        'data_source': {
            'kind': 'runtime_snapshot',
            'endpoint': '/api/runtime/health',
            'refresh_seconds': 60,
        },
        'cards': [
            {
                'id': 'runtime-status',
                'title': 'Runtime Status',
                'type': 'status',
                'value': snapshot['status'],
                'severity': snapshot['status'],
                'drilldown': '/api/runtime/health',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime'}),
            },
            {
                'id': 'risk-score',
                'title': 'Risk Score',
                'type': 'metric',
                'value': snapshot['risk_score'],
                'unit': 'score',
                'min': 0,
                'max': 100,
                'drilldown': '/api/runtime/metrics',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'metrics'}),
            },
            {
                'id': 'pending-items',
                'title': 'Pendencias Operacionais',
                'type': 'metric',
                'value': snapshot['critical_counts']['pending_items'],
                'unit': 'itens',
                'drilldown': '/monitoramento-operacional',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'estado': 'amarelo', 'secao': 'itens'}),
            },
            {
                'id': 'uptime',
                'title': 'Uptime',
                'type': 'metric',
                'value': snapshot['uptime_seconds'],
                'unit': 'seconds',
                'drilldown': '/api/runtime/liveness',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime'}),
            },
            {
                'id': 'readiness-percent',
                'title': 'Readiness Operacional',
                'type': 'metric',
                'value': 100 if _runtime_ready(snapshot) else 75,
                'unit': 'percent',
                'min': 0,
                'max': 100,
                'drilldown': '/api/runtime/readiness',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime', 'estado': 'amarelo'}),
            },
            {
                'id': 'fly-duckdns-status',
                'title': 'Fly/DuckDNS',
                'type': 'status',
                'value': 'pending_public_evidence',
                'severity': 'attention',
                'drilldown': '/api/runtime/contracts',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime'}),
            },
            {
                'id': 'governance-evidence-score',
                'title': 'Governanca Evidenciada',
                'type': 'metric',
                'value': governance_index.get('governance_evidence_score', 0),
                'unit': 'score',
                'min': 0,
                'max': 100,
                'severity': governance_index.get('overall_status', 'unknown'),
                'drilldown': '/monitoramento-operacional',
                'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'governanca'}),
            },
            *governance_cards,
            *trilha_d_cards,
            *continuous_monitoring_cards,
            *continuous_monitoring_history_cards,
            *merge_readiness_history_cards,
            *mesh_cards,
        ],
        'governance_evidence': governance_index,
        'trilha_d_history': trilha_d_index,
        'continuous_trilha_d_monitoring': continuous_monitoring_index,
        'continuous_trilha_d_monitoring_history': continuous_monitoring_history_index,
        'merge_readiness_history': merge_readiness_history_index,
        'operational_mesh': mesh_signal,
        'cross_runtime_analytics': cross_runtime,
        'sections': [
            {
                'id': 'workflow-topology',
                'title': 'Topology Operacional',
                'type': 'timeline',
                'items': [
                    {
                        'step': 'health',
                        'label': 'Runtime Health',
                        'status': snapshot['status'],
                        'href': '/api/runtime/health',
                        'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime'}),
                    },
                    {
                        'step': 'readiness',
                        'label': 'Readiness Gate',
                        'status': _runtime_readiness_reason(snapshot),
                        'href': '/api/runtime/readiness',
                        'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'runtime', 'estado': 'amarelo'}),
                    },
                    {
                        'step': 'metrics',
                        'label': 'Prometheus Metrics',
                        'status': 'available',
                        'href': '/api/runtime/metrics',
                        'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'metrics'}),
                    },
                    {
                        'step': 'monitoring',
                        'label': 'Analitico Operacional',
                        'status': snapshot['operational_summary']['estado_geral'],
                        'href': '/monitoramento-operacional',
                        'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'itens'}),
                    },
                ],
            },
            {
                'id': 'public-smoke',
                'title': 'Public Smoke Tests',
                'type': 'links',
                'items': [
                    {'label': 'Root', 'href': '/'},
                    {'label': 'Health', 'href': '/health'},
                    {'label': 'Runtime Health', 'href': '/api/runtime/health'},
                    {'label': 'Readiness', 'href': '/api/runtime/readiness'},
                    {'label': 'Liveness', 'href': '/api/runtime/liveness'},
                    {'label': 'Metrics', 'href': '/api/runtime/metrics'},
                ],
            },
            {
                'id': 'operational-timeline',
                'title': 'Timeline Operacional',
                'type': 'timeline',
                'items': [
                    {'step': 'smoke', 'label': 'Smoke público', 'status': 'artifact_required', 'href': '/api/runtime/health'},
                    {'step': 'readiness', 'label': 'Readiness consolidado', 'status': _runtime_readiness_reason(snapshot), 'href': '/api/runtime/readiness'},
                    {'step': 'incident-summary', 'label': 'Resumo de incidentes', 'status': 'no_open_runtime_incident_in_snapshot', 'href': '/api/runtime/analytics'},
                    {'step': 'risk-summary', 'label': 'Resumo de risco', 'status': snapshot['status'], 'href': '/api/runtime/metrics'},
                    {'step': 'environment-drift', 'label': 'Drift de ambientes', 'status': 'requires_public_artifacts', 'href': '/api/runtime/dashboard'},
                ],
            },
            {
                'id': 'environment-evidence',
                'title': 'Runtime Environment Evidence',
                'type': 'environment_status',
                'items': [
                    {'environment': 'dev', 'status': 'partial', 'source': 'local_runtime_contract'},
                    {'environment': 'staging', 'status': 'unavailable', 'source': 'public_artifact_pending'},
                    {'environment': 'prod', 'status': 'degraded' if snapshot['status'] == 'degraded' else 'partial', 'source': 'runtime_health_snapshot'},
                ],
            },
            {
                'id': 'incident-summary',
                'title': 'Incident Summary',
                'type': 'summary',
                'items': {'open_incidents': 0, 'runtime_status': snapshot['status'], 'risk_score': snapshot['risk_score']},
            },
            {
                'id': 'risk-summary',
                'title': 'Risk Summary',
                'type': 'summary',
                'items': {'risk_score': snapshot['risk_score'], 'pending_items': snapshot['critical_counts']['pending_items'], 'blocked_items': snapshot['critical_counts']['blocked_items']},
            },
            {
                'id': 'environment-drift-summary',
                'title': 'Environment Drift Summary',
                'type': 'summary',
                'items': {'classification': 'requires_public_artifacts', 'environments': ['dev', 'staging', 'prod']},
            },
            governance_section,
            trilha_d_section,
            continuous_monitoring_section,
            continuous_monitoring_history_section,
            merge_readiness_history_section,
            mesh_section,
            {
                'id': 'correlation-analytics',
                'title': 'Correlation Analytics',
                'type': 'summary',
                'items': correlation_report,
            },
            {
                'id': 'runtime-topology-preview',
                'title': 'Runtime Topology Preview',
                'type': 'graph_preview',
                'items': topology,
            },
            {
                'id': 'observability-readiness',
                'title': 'Observability Readiness',
                'type': 'summary',
                'items': observability_report,
            },
        ],
        'guardrails': {
            'no_secrets': True,
            'no_pii': True,
            'read_only': True,
            'deploy_gate_relaxed': snapshot['evidence'].get('deploy_gate_relaxed', False),
        },
    }


def _metric_label_value(value: str) -> str:
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')


def _metric_line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        labels_text = ','.join(f'{key}="{_metric_label_value(value)}"' for key, value in sorted(labels.items()))
        return f'{name}{{{labels_text}}} {value}'
    return f'{name} {value}'


@router.get('/monitoramento-operacional')
def obter_monitoramento_operacional(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = criar_snapshot_operacional(correlation_id)
    return ok(snapshot.model_dump(), correlation_id)


@router.get('/api/runtime/health')
def obter_api_runtime_health(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    return ok(_criar_runtime_observability_snapshot(correlation_id), correlation_id)


@router.get('/api/runtime/dashboard')
def obter_api_runtime_dashboard(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    return ok(_criar_runtime_dashboard_schema(snapshot), correlation_id)


@router.get('/api/runtime/operational-mesh')
def obter_api_runtime_operational_mesh(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    payload = montar_payload_operational_mesh()
    payload['correlation_id'] = correlation_id
    return ok(payload, correlation_id)


@router.get('/api/runtime/readiness')
def obter_api_runtime_readiness(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    ready = _runtime_ready(snapshot)
    return ok({'ready': ready, 'readiness_reason': _runtime_readiness_reason(snapshot), **snapshot}, correlation_id)


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
        '# HELP reqsys_http_requests_total HTTP requests by feature.',
        '# TYPE reqsys_http_requests_total counter',
    ]
    feature_items = REGISTRY.snapshot()
    for item in feature_items:
        feature_labels = {**labels, 'feature': item.feature}
        lines.append(_metric_line('reqsys_http_requests_total', item.requests_total, feature_labels))
    if feature_items:
        lines.extend(
            [
                '# HELP reqsys_http_errors_total HTTP errors by feature.',
                '# TYPE reqsys_http_errors_total counter',
            ]
        )
        for item in feature_items:
            feature_labels = {**labels, 'feature': item.feature}
            lines.append(_metric_line('reqsys_http_errors_total', item.errors_total, feature_labels))
        lines.extend(
            [
                '# HELP reqsys_http_duration_ms_total HTTP duration in milliseconds by feature.',
                '# TYPE reqsys_http_duration_ms_total counter',
            ]
        )
        for item in feature_items:
            feature_labels = {**labels, 'feature': item.feature}
            lines.append(_metric_line('reqsys_http_duration_ms_total', item.duration_ms_total, feature_labels))
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
