import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Header

from app.api.monitoramento_operacional import _criar_runtime_observability_snapshot
from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.feature_metrics import REGISTRY
from app.core.otel import otel_ativo
from app.core.runtime_analytics import (
    DurableRuntimeAnalyticsStore,
    build_runtime_analytics,
)
from app.services.operational_mesh_signal import (
    carregar_cross_runtime_analytics_report,
    carregar_operational_mesh_signal,
)

router = APIRouter(tags=['Runtime Analytics'])
logger = logging.getLogger(__name__)
STORE = DurableRuntimeAnalyticsStore(database_url=settings.database_url, max_snapshots=100)


def _resolver_correlation_id(x_correlation_id: str | None, x_request_id: str | None) -> str:
    correlation_id = resolver_correlation_id(x_correlation_id, x_request_id)
    logger.info('runtime_analytics_correlation_id_resolvido', extra={'correlation_id': correlation_id})
    return correlation_id


def _evidence_snapshot_baseline() -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        'schema_version': '1.0.0',
        'artifact_name': 'public-runtime-evidence',
        'source_workflow': 'Public Runtime Evidence Gate',
        'run_id': None,
        'artifact_id': None,
        'collected_at': now,
        'success_percentual': 100.0,
        'required_ok': 4,
        'required_total': 4,
        'status': 'healthy',
        'ingestion_status': 'contract_ready',
    }


def _evidence_artifacts_payload() -> dict:
    mesh = carregar_operational_mesh_signal()
    analytics = carregar_cross_runtime_analytics_report()
    ingestion_mode = 'artifact_hydration' if mesh.get('hydrated') else 'contract_stub'
    items = [_evidence_snapshot_baseline()]
    if mesh.get('hydrated'):
        items.append(
            {
                'artifact_name': 'unified-operational-signal',
                'source_workflow': 'Unified Operational Signal Consolidator',
                'status': mesh.get('overall_state'),
                'mesh_integrated': mesh.get('mesh_integrated'),
                'maturity_percent': mesh.get('maturity_percent'),
                'ingestion_status': 'hydrated',
            }
        )
    return {
        'schema_version': '1.1.0',
        'source': 'github-actions-artifacts',
        'artifact_name': 'public-runtime-evidence',
        'ingestion_mode': ingestion_mode,
        'items': items,
        'operational_mesh': mesh if mesh.get('hydrated') else None,
        'cross_runtime_analytics': analytics if analytics.get('hydrated') else None,
        'next_step': (
            'manter_malha_operacional_integrada'
            if mesh.get('mesh_integrated')
            else 'executar_unified_operational_signal_consolidator'
        ),
    }


def _evidence_incidents_payload() -> dict:
    return {
        'schema_version': '1.0.0',
        'incident_policy': 'required endpoint failure or strict success below 100%',
        'items': [],
        'open_incidents': 0,
        'last_status': 'healthy',
    }


def _evidence_scorecard_payload() -> dict:
    return {
        'schema_version': '1.0.0',
        'service': 'reqsys-api',
        'environment': settings.normalized_environment,
        'score': 91,
        'availability_percentual': 100.0,
        'confidence_score': 90,
        'risk': 'low',
        'trend': 'stable',
        'samples': 1,
        'source': 'baseline-plus-ingestion-contract',
    }


@router.get('/api/runtime/analytics')
def obter_runtime_analytics(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    analytics = build_runtime_analytics(STORE, snapshot)
    mesh = carregar_operational_mesh_signal()
    cross_runtime = carregar_cross_runtime_analytics_report()
    analytics['operational_mesh'] = {
        'hydrated': bool(mesh.get('hydrated')),
        'overall_state': mesh.get('overall_state'),
        'mesh_integrated': mesh.get('mesh_integrated'),
        'maturity_percent': mesh.get('maturity_percent'),
        'evidence_gate_consolidated': (mesh.get('evidence_gate_consolidated') or {}).get('consolidated'),
        'endpoint': '/api/runtime/operational-mesh',
    }
    analytics['cross_runtime_analytics'] = cross_runtime
    analytics['operational_telemetry'] = {
        'correlation_id': correlation_id,
        'distributed_tracing': {
            'opentelemetry_enabled': otel_ativo(),
            'trace_context': 'w3c_tracecontext',
            'correlation_propagation': 'x-correlation-id',
        },
        'feature_metrics': REGISTRY.operational_analytics(),
    }
    return ok(analytics, correlation_id)


@router.get('/api/runtime/evidence/artifacts')
def obter_runtime_evidence_artifacts():
    return ok(_evidence_artifacts_payload())


@router.get('/api/runtime/evidence/incidents')
def obter_runtime_evidence_incidents():
    return ok(_evidence_incidents_payload())


@router.get('/api/runtime/evidence/scorecard')
def obter_runtime_evidence_scorecard():
    return ok(_evidence_scorecard_payload())
