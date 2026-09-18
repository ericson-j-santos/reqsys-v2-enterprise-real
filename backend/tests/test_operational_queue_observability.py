import pytest

from app.core.operational_queue import OperationalQueue, OperationalQueueUnavailableError
from app.core.operational_queue_observability import (
    OperationalQueueObserver,
)


def test_pending_count_supports_redis_response_shapes():
    assert OperationalQueueObserver._pending_count({'pending': 4}) == 4
    assert OperationalQueueObserver._pending_count([3, '1-0', '2-0', []]) == 3
    assert OperationalQueueObserver._pending_count(None) == 0


def test_observer_rejects_invalid_inactive_threshold():
    with pytest.raises(ValueError, match='maior que zero'):
        OperationalQueueObserver(inactive_consumer_ms=0)


@pytest.mark.asyncio
async def test_observer_fails_closed_without_redis_streams():
    observer = OperationalQueueObserver(queue=OperationalQueue())

    with pytest.raises(
        OperationalQueueUnavailableError,
        match='OPERATIONAL_QUEUE_PROVIDER=redis_streams',
    ):
        await observer.snapshot()
