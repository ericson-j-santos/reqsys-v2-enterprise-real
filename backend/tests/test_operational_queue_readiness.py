import pytest

from app.core.operational_queue_readiness import OperationalQueueReadinessPolicy


def test_readiness_is_ready_within_thresholds():
    policy = OperationalQueueReadinessPolicy(
        max_lag=10,
        max_pending=5,
        max_inactive_consumers=0,
    )

    result = policy.evaluate(
        {
            'status': 'healthy',
            'lag': 10,
            'pending': 5,
            'consumers_inactive': 0,
            'timestamp': '2026-07-24T15:00:00+00:00',
        }
    )

    assert result['ready'] is True
    assert result['status'] == 'ready'
    assert result['reasons'] == []


def test_readiness_blocks_when_thresholds_are_exceeded():
    policy = OperationalQueueReadinessPolicy(
        max_lag=10,
        max_pending=5,
        max_inactive_consumers=0,
    )

    result = policy.evaluate(
        {
            'status': 'degraded',
            'lag': 11,
            'pending': 6,
            'consumers_inactive': 1,
        }
    )

    assert result['ready'] is False
    assert result['status'] == 'not_ready'
    assert result['reasons'] == [
        'lag_threshold_exceeded',
        'pending_threshold_exceeded',
        'inactive_consumers_threshold_exceeded',
    ]


def test_readiness_preserves_critical_observability_reasons():
    result = OperationalQueueReadinessPolicy().evaluate(
        {
            'status': 'critical',
            'reasons': ['pending_without_consumers'],
            'lag': 0,
            'pending': 1,
            'consumers_inactive': 0,
        }
    )

    assert result['ready'] is False
    assert result['reasons'] == ['pending_without_consumers']


def test_readiness_policy_loads_environment(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_QUEUE_READY_MAX_LAG', '250')
    monkeypatch.setenv('OPERATIONAL_QUEUE_READY_MAX_PENDING', '75')
    monkeypatch.setenv('OPERATIONAL_QUEUE_READY_MAX_INACTIVE_CONSUMERS', '2')

    policy = OperationalQueueReadinessPolicy.from_environment()

    assert policy.max_lag == 250
    assert policy.max_pending == 75
    assert policy.max_inactive_consumers == 2


def test_readiness_policy_rejects_negative_values(monkeypatch):
    monkeypatch.setenv('OPERATIONAL_QUEUE_READY_MAX_PENDING', '-1')

    with pytest.raises(ValueError, match='maior ou igual a zero'):
        OperationalQueueReadinessPolicy.from_environment()
