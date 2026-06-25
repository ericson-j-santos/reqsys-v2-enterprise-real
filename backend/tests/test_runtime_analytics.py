from fastapi.testclient import TestClient

from app.core.runtime_analytics import RuntimeAnalyticsStore, build_runtime_analytics
from app.main import app


def _snapshot(correlation_id: str, status: str = 'attention', risk_score: int = 10) -> dict:
    return {
        'correlation_id': correlation_id,
        'generated_at': '2026-06-25T00:00:00+00:00',
        'status': status,
        'risk_score': risk_score,
        'critical_counts': {
            'blocked_items': 0,
            'pending_items': 1,
            'total_items': 3,
        },
        'evidence': {
            'no_secrets': True,
            'no_pii': True,
        },
    }


def test_runtime_analytics_store_respeita_limite():
    store = RuntimeAnalyticsStore(max_snapshots=2)
    store.record(_snapshot('one', risk_score=10))
    store.record(_snapshot('two', risk_score=20))
    store.record(_snapshot('three', risk_score=30))

    snapshots = store.list_snapshots()
    assert len(snapshots) == 2
    assert snapshots[0]['correlation_id'] == 'two'
    assert snapshots[1]['correlation_id'] == 'three'


def test_build_runtime_analytics_calcula_metricas_temporais():
    store = RuntimeAnalyticsStore(max_snapshots=10)
    build_runtime_analytics(store, _snapshot('one', status='attention', risk_score=10))
    analytics = build_runtime_analytics(store, _snapshot('two', status='degraded', risk_score=30))

    assert analytics['schema_version'] == '1.0.0'
    assert analytics['window']['total_snapshots'] == 2
    assert analytics['summary']['failure_rate'] == 50.0
    assert analytics['summary']['availability_score'] == 50.0
    assert analytics['summary']['average_risk_score'] == 20
    assert analytics['trends']['risk_score'] == 'degrading'
    assert analytics['guardrails']['durable_storage_enabled'] is False
    assert analytics['mttr']['status'] == 'pending_persistent_storage'


def test_runtime_analytics_endpoint_expõe_historico_governado():
    correlation_id = 'corr-runtime-analytics-test'
    res = TestClient(app).get('/api/runtime/analytics', headers={'X-Correlation-ID': correlation_id})

    assert res.status_code == 200
    body = res.json()
    data = body['data']
    assert body['meta']['correlation_id'] == correlation_id
    assert data['correlation_id'] == correlation_id
    assert data['schema_version'] == '1.0.0'
    assert data['window']['mode'] == 'in_memory_rolling'
    assert data['window']['total_snapshots'] >= 1
    assert 0 <= data['summary']['failure_rate'] <= 100
    assert 0 <= data['summary']['availability_score'] <= 100
    assert data['guardrails']['no_secrets'] is True
    assert data['guardrails']['read_only'] is True


def test_public_root_expoe_runtime_analytics_link():
    res = TestClient(app).get('/')

    assert res.status_code == 200
    body = res.json()
    assert body['data']['runtime_analytics'] == '/api/runtime/analytics'
