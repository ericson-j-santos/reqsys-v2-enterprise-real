import pytest
from fastapi import HTTPException

from app.api import operational_autonomy
from app.core.operational_queue import OperationalQueueUnavailableError


@pytest.mark.asyncio
async def test_operational_queue_consumers_returns_enveloped_snapshot(monkeypatch):
    expected = {
        'schema_version': '1.0.0',
        'component': 'operational_queue_consumers',
        'status': 'healthy',
        'pending': 0,
        'lag': 0,
    }

    async def fake_snapshot(self):
        return expected

    monkeypatch.setattr(operational_autonomy.OperationalQueueObserver, 'snapshot', fake_snapshot)

    response = await operational_autonomy.operational_queue_consumers()

    assert response['success'] is True
    assert response['data'] == expected


@pytest.mark.asyncio
async def test_operational_queue_consumers_returns_503_when_unavailable(monkeypatch):
    async def fake_snapshot(self):
        raise OperationalQueueUnavailableError('redis indisponível')

    monkeypatch.setattr(operational_autonomy.OperationalQueueObserver, 'snapshot', fake_snapshot)

    with pytest.raises(HTTPException) as exc_info:
        await operational_autonomy.operational_queue_consumers()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == 'redis indisponível'


@pytest.mark.asyncio
async def test_health_embeds_consumer_observability_for_connected_redis(monkeypatch):
    async def fake_queue_snapshot():
        return {
            'schema_version': '2.0.0',
            'provider': 'redis_streams',
            'connected': True,
        }

    async def fake_observer_snapshot(self):
        return {
            'schema_version': '1.0.0',
            'component': 'operational_queue_consumers',
            'status': 'degraded',
            'reasons': ['inactive_consumers'],
        }

    monkeypatch.setattr(operational_autonomy.operational_queue, 'snapshot', fake_queue_snapshot)
    monkeypatch.setattr(operational_autonomy.OperationalQueueObserver, 'snapshot', fake_observer_snapshot)

    response = await operational_autonomy.operational_autonomy_health()

    assert response['success'] is True
    assert response['data']['consumer_observability']['status'] == 'degraded'


@pytest.mark.asyncio
async def test_health_keeps_base_snapshot_when_provider_is_memory(monkeypatch):
    async def fake_queue_snapshot():
        return {
            'schema_version': '2.0.0',
            'provider': 'memory',
            'connected': True,
        }

    monkeypatch.setattr(operational_autonomy.operational_queue, 'snapshot', fake_queue_snapshot)

    response = await operational_autonomy.operational_autonomy_health()

    assert response['data']['consumer_observability'] is None
    assert response['data']['runtime_mode'] == 'memory'
