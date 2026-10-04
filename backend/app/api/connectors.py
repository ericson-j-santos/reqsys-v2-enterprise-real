from fastapi import APIRouter, Header

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.services.connection_broker import montar_health_payload

router = APIRouter(tags=['Connection Broker'])


def _correlation_id(x_correlation_id: str | None, x_request_id: str | None) -> str:
    return resolver_correlation_id(x_correlation_id, x_request_id)


@router.get('/api/connectors/health')
def obter_connectors_health(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = _correlation_id(x_correlation_id, x_request_id)
    payload = montar_health_payload(correlation_id)
    return ok(payload, correlation_id)
