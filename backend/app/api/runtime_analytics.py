import logging
from uuid import uuid4

from fastapi import APIRouter, Header

from app.api.monitoramento_operacional import _criar_runtime_observability_snapshot
from app.core.config import settings
from app.core.envelope import ok
from app.core.runtime_analytics import DurableRuntimeAnalyticsStore, build_runtime_analytics

router = APIRouter(tags=['Runtime Analytics'])
logger = logging.getLogger(__name__)
STORE = DurableRuntimeAnalyticsStore(database_url=settings.database_url, max_snapshots=100)


def _resolver_correlation_id(x_correlation_id: str | None, x_request_id: str | None) -> str:
    correlation_id = x_correlation_id or x_request_id or str(uuid4())
    logger.info('runtime_analytics_correlation_id_resolvido', extra={'correlation_id': correlation_id})
    return correlation_id


@router.get('/api/runtime/analytics')
def obter_runtime_analytics(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _resolver_correlation_id(x_correlation_id, x_request_id)
    snapshot = _criar_runtime_observability_snapshot(correlation_id)
    analytics = build_runtime_analytics(STORE, snapshot)
    return ok(analytics, correlation_id)
