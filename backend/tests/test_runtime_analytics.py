from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.runtime_analytics import (
    DurableRuntimeAnalyticsStore,
    RuntimeAnalyticsStore,
    build_lead_time,
    build_mttr,
    build_runtime_analytics,
)
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
            'incident_key': 'runtime-health-test',
        },
    }


def _snapshot_with_deploy_event(correlation_id: str, deploy_event: dict) -> dict:
    snapshot = _snapshot(correlation_id)
    snapshot['evidence']['deploy_event'] = deploy_event
    return snapshot


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

    assert analytics['schema_version'] == '1.3.0'
    assert analytics['window']['total_snapshots'] == 2
    assert analytics['window']['mode'] == 'in_memory_rolling'
    assert analytics['summary']['failure_rate'] == 50.0
    assert analytics['summary']['availability_score'] == 50.0
    assert analytics['summary']['average_risk_score'] == 20
    assert analytics['trends']['risk_score'] == 'degrading'
    assert analytics['guardrails']['durable_storage_enabled'] is False
    assert analytics['guardrails']['incident_lifecycle_enabled'] is True
    assert analytics['guardrails']['deploy_lifecycle_enabled'] is True
    assert analytics['mttr']['status'] == 'insufficient_resolved_incidents'
    assert analytics['lead_time']['status'] == 'insufficient_deploy_events'


def test_incident_lifecycle_abre_reconhece_e_resolve_incidente():
    store = RuntimeAnalyticsStore(max_snapshots=10)
    opened = build_runtime_analytics(store, _snapshot('one', status='degraded', risk_score=80))
    acknowledged = build_runtime_analytics(store, _snapshot('two', status='blocked', risk_score=90))
    resolved = build_runtime_analytics(store, _snapshot('three', status='healthy', risk_score=5))

    events = resolved['incident_lifecycle']['events']
    assert [event['event_type'] for event in events] == [
        'incident_opened',
        'incident_acknowledged',
        'incident_resolved',
    ]
    assert opened['incident_lifecycle']['last_event']['event_type'] == 'incident_opened'
    assert acknowledged['incident_lifecycle']['last_event']['event_type'] == 'incident_acknowledged'
    assert resolved['incident_lifecycle']['last_event']['event_type'] == 'incident_resolved'
    assert resolved['mttr']['status'] == 'calculated'
    assert resolved['mttr']['resolved_incidents'] == 1
    assert resolved['mttr']['value_seconds'] >= 0


def test_build_mttr_calcula_ciclo_resolvido():
    opened_at = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    resolved_at = datetime(2026, 6, 25, 10, 5, 30, tzinfo=timezone.utc).isoformat()
    mttr = build_mttr(
        [
            {
                'incident_key': 'runtime-health-test',
                'event_type': 'incident_opened',
                'event_at': opened_at,
            },
            {
                'incident_key': 'runtime-health-test',
                'event_type': 'incident_resolved',
                'event_at': resolved_at,
            },
        ]
    )

    assert mttr['status'] == 'calculated'
    assert mttr['value_seconds'] == 330
    assert mttr['min_seconds'] == 330
    assert mttr['max_seconds'] == 330


def test_build_lead_time_calcula_ciclo_deploy_resolvido():
    started_at = datetime(2026, 6, 25, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    finished_at = datetime(2026, 6, 25, 9, 7, 30, tzinfo=timezone.utc).isoformat()
    lead_time = build_lead_time(
        [
            {
                'deploy_key': 'deploy-main-001',
                'event_type': 'deploy_started',
                'event_at': started_at,
            },
            {
                'deploy_key': 'deploy-main-001',
                'event_type': 'deploy_finished',
                'event_at': finished_at,
            },
        ]
    )

    assert lead_time['status'] == 'calculated'
    assert lead_time['value_seconds'] == 450
    assert lead_time['min_seconds'] == 450
    assert lead_time['max_seconds'] == 450


def test_deploy_lifecycle_calcula_lead_time_por_snapshot():
    store = RuntimeAnalyticsStore(max_snapshots=10)
    started_at = datetime(2026, 6, 25, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    finished_at = datetime(2026, 6, 25, 9, 7, 30, tzinfo=timezone.utc).isoformat()

    build_runtime_analytics(
        store,
        _snapshot_with_deploy_event(
            'deploy-one',
            {
                'event_type': 'deploy_started',
                'deploy_key': 'deploy-main-001',
                'environment': 'production',
                'event_at': started_at,
                'commit_sha': 'abc123',
            },
        ),
    )
    analytics = build_runtime_analytics(
        store,
        _snapshot_with_deploy_event(
            'deploy-two',
            {
                'event_type': 'deploy_finished',
                'deploy_key': 'deploy-main-001',
                'environment': 'production',
                'event_at': finished_at,
                'commit_sha': 'abc123',
            },
        ),
    )

    assert [event['event_type'] for event in analytics['deploy_lifecycle']['events']] == [
        'deploy_started',
        'deploy_finished',
    ]
    assert analytics['deploy_lifecycle']['last_event']['event_type'] == 'deploy_finished'
    assert analytics['lead_time']['status'] == 'calculated'
    assert analytics['lead_time']['value_seconds'] == 450
    assert analytics['lead_time']['finished_deploys'] == 1


def test_durable_runtime_analytics_store_persiste_snapshots(tmp_path):
    db_path = tmp_path / 'runtime-analytics.db'
    database_url = f'sqlite:///{db_path}'
    store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)

    build_runtime_analytics(store, _snapshot('one', status='attention', risk_score=10))
    analytics = build_runtime_analytics(store, _snapshot('two', status='degraded', risk_score=30))

    assert db_path.exists()
    assert analytics['schema_version'] == '1.3.0'
    assert analytics['window']['mode'] == 'durable_sql'
    assert analytics['window']['total_snapshots'] == 2
    assert analytics['summary']['failure_rate'] == 50.0
    assert analytics['summary']['availability_score'] == 50.0
    assert analytics['guardrails']['durable_storage_enabled'] is True
    assert analytics['guardrails']['storage_mode'] == 'durable_sql'

    reloaded_store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)
    persisted = reloaded_store.list_snapshots()
    assert [item['correlation_id'] for item in persisted] == ['one', 'two']


def test_durable_runtime_analytics_store_persiste_incident_events(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'runtime-analytics.db'}"
    store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)

    build_runtime_analytics(store, _snapshot('one', status='degraded', risk_score=80))
    build_runtime_analytics(store, _snapshot('two', status='blocked', risk_score=90))
    analytics = build_runtime_analytics(store, _snapshot('three', status='healthy', risk_score=5))

    assert analytics['mttr']['status'] == 'calculated'
    reloaded_store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)
    persisted_events = reloaded_store.list_incident_events()
    assert [event['event_type'] for event in persisted_events] == [
        'incident_opened',
        'incident_acknowledged',
        'incident_resolved',
    ]


def test_durable_runtime_analytics_store_persiste_deploy_events(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'runtime-analytics.db'}"
    store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)
    started_at = datetime(2026, 6, 25, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    finished_at = datetime(2026, 6, 25, 9, 7, 30, tzinfo=timezone.utc).isoformat()

    store.record_deploy_event(
        {
            'event_type': 'deploy_started',
            'deploy_key': 'deploy-main-001',
            'environment': 'production',
            'event_at': started_at,
        }
    )
    store.record_deploy_event(
        {
            'event_type': 'deploy_finished',
            'deploy_key': 'deploy-main-001',
            'environment': 'production',
            'event_at': finished_at,
        }
    )

    reloaded_store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=10)
    persisted_events = reloaded_store.list_deploy_events()
    assert [event['event_type'] for event in persisted_events] == ['deploy_started', 'deploy_finished']
    assert build_lead_time(persisted_events)['value_seconds'] == 450


def test_durable_runtime_analytics_store_sanitiza_payload(tmp_path):
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'runtime-analytics.db'}", max_snapshots=10)
    snapshot = _snapshot('safe')
    snapshot['secret_token'] = 'nao-deve-persistir'
    snapshot['cpf'] = '00000000000'

    store.record(snapshot)

    persisted = store.list_snapshots()[0]
    assert 'secret_token' not in persisted
    assert 'cpf' not in persisted
    assert persisted['correlation_id'] == 'safe'


def test_runtime_analytics_endpoint_expõe_historico_governado():
    correlation_id = 'corr-runtime-analytics-test'
    res = TestClient(app).get('/api/runtime/analytics', headers={'X-Correlation-ID': correlation_id})

    assert res.status_code == 200
    body = res.json()
    data = body['data']
    assert body['meta']['correlation_id'] == correlation_id
    assert data['correlation_id'] == correlation_id
    assert data['schema_version'] == '1.3.0'
    assert data['window']['mode'] == 'durable_sql'
    assert data['window']['total_snapshots'] >= 1
    assert data['window']['total_deploy_events'] >= 0
    assert 0 <= data['summary']['failure_rate'] <= 100
    assert 0 <= data['summary']['availability_score'] <= 100
    assert data['guardrails']['no_secrets'] is True
    assert data['guardrails']['read_only'] is True
    assert data['guardrails']['durable_storage_enabled'] is True
    assert data['guardrails']['incident_lifecycle_enabled'] is True
    assert data['guardrails']['deploy_lifecycle_enabled'] is True
    assert 'incident_lifecycle' in data
    assert 'deploy_lifecycle' in data


def test_public_root_expoe_runtime_analytics_link():
    res = TestClient(app).get('/')

    assert res.status_code == 200
    body = res.json()
    assert body['data']['runtime_analytics'] == '/api/runtime/analytics'
