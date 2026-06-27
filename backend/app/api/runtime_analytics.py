import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Header

from app.api.monitoramento_operacional import _criar_runtime_observability_snapshot
from app.core.config import settings
from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.core.feature_metrics import REGISTRY
from app.core.observability_gold_standard import avaliar_trilha_b
from app.core.otel import otel_ativo
from app.core.runtime_analytics import (
    DurableRuntimeAnalyticsStore,
    build_runtime_analytics,
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
    return {
        'schema_version': '1.0.0',
        'source': 'github-actions-artifacts',
        'artifact_name': 'public-runtime-evidence',
        'ingestion_mode': 'contract_stub',
        'items': [_evidence_snapshot_baseline()],
        'next_step': 'connect GitHub Actions artifact reader to hydrate real historical snapshots',
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
    analytics['operational_telemetry'] = {
        'correlation_id': correlation_id,
        'distributed_tracing': {
            'opentelemetry_enabled': otel_ativo(),
            'trace_context': 'w3c_tracecontext',
            'correlation_propagation': 'x-correlation-id',
        },
        'feature_metrics': REGISTRY.operational_analytics(),
        'trilha_b_gold_standard': avaliar_trilha_b(),
    }
    return ok(analytics, correlation_id)


@router.get('/api/runtime/observability/gold-standard')
def obter_trilha_b_gold_standard(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    return ok(avaliar_trilha_b(), correlation_id)


@router.get('/api/runtime/evidence/artifacts')
def obter_runtime_evidence_artifacts():
    return ok(_evidence_artifacts_payload())


@router.get('/api/runtime/evidence/incidents')
def obter_runtime_evidence_incidents():
    return ok(_evidence_incidents_payload())


@router.get('/api/runtime/evidence/scorecard')
def obter_runtime_evidence_scorecard():
    return ok(_evidence_scorecard_payload())
