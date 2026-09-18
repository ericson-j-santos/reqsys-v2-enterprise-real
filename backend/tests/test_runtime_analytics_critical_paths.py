"""Caminhos críticos — runtime analytics (helpers, durable store e relatórios)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.runtime_analytics import (
    DurableRuntimeAnalyticsStore,
    RuntimeAnalyticsStore,
    _deploy_key,
    _deployment_environment,
    _incident_key,
    _parse_dt,
    _sanitize_snapshot,
    _to_iso,
    _trend,
    build_correlation_report,
    build_incident_event,
    build_lead_time,
    build_mttr,
    build_observability_report,
    build_runtime_topology,
    extract_deploy_event,
    sanitize_deploy_event,
)


def test_runtime_analytics_store_rejeita_max_snapshots_invalido():
    with pytest.raises(ValueError, match='max_snapshots'):
        RuntimeAnalyticsStore(max_snapshots=0)


def test_durable_store_rejeita_max_snapshots_invalido():
    with pytest.raises(ValueError, match='max_snapshots'):
        DurableRuntimeAnalyticsStore(database_url='sqlite:///:memory:', max_snapshots=0)


def test_parse_dt_aceita_datetime_e_iso_e_rejeita_invalido():
    dt = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    assert _parse_dt(dt) == dt
    assert _parse_dt('2026-06-30T12:00:00Z') is not None
    assert _parse_dt('invalido') is None
    assert _parse_dt(None) is None
    assert _parse_dt(12345) is None


def test_to_iso_converte_datetime_e_string():
    dt = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    assert _to_iso(dt).endswith('+00:00')
    assert _to_iso('texto') == 'texto'


def test_sanitize_snapshot_filtra_campos_nao_allowlisted():
    payload = _sanitize_snapshot(
        {
            'correlation_id': 'corr-1',
            'status': 'attention',
            'risk_score': 10,
            'critical_counts': {'pending_items': 1},
            'evidence': {'no_pii': True},
            'secret': 'nao-deve-aparecer',
        }
    )
    assert payload['correlation_id'] == 'corr-1'
    assert 'secret' not in payload
    assert payload['critical_counts'] == {'pending_items': 1}


def test_incident_key_prioriza_runtime_component():
    snapshot = {'evidence': {'runtime_component': 'mesh-signal'}}
    assert _incident_key(snapshot) == 'mesh-signal'


def test_deploy_key_e_environment_com_fallbacks():
    assert _deploy_key({'version': 'v1.2.3'}) == 'v1.2.3'
    assert _deploy_key({}) == 'runtime-deploy'
    assert _deployment_environment({'target_environment': 'staging'}) == 'staging'
    assert _deployment_environment({}) == 'unknown'


def test_build_incident_event_retorna_none_quando_sem_transicao():
    snapshot = {'status': 'healthy', 'risk_score': 0, 'critical_counts': {}, 'evidence': {}}
    assert build_incident_event(snapshot, []) is None


def test_sanitize_deploy_event_rejeita_tipo_desconhecido():
    assert sanitize_deploy_event({'event_type': 'invalid'}) is None


def test_sanitize_deploy_event_normaliza_deployment_started():
    event = sanitize_deploy_event(
        {
            'event_type': 'deployment_started',
            'deploy_key': 'deploy-abc',
            'environment': 'dev',
            'correlation_id': 'corr-deploy',
            'commit_sha': 'sha123',
        }
    )
    assert event is not None
    assert event['event_type'] == 'deploy_started'
    assert event['deploy_key'] == 'deploy-abc'
    assert event['environment'] == 'dev'


def test_extract_deploy_event_lê_deployment_event():
    snapshot = {'evidence': {'deployment_event': {'event_type': 'deploy_started'}}}
    assert extract_deploy_event(snapshot) == {'event_type': 'deploy_started'}


def test_trend_classifica_improving_degrading_e_insufficient():
    assert _trend([80]) == 'insufficient_data'
    assert _trend([80, 70]) == 'improving'
    assert _trend([10, 30]) == 'degrading'
    assert _trend([50, 52]) == 'stable'


def test_in_memory_store_record_deploy_event_rejeita_invalido():
    store = RuntimeAnalyticsStore(max_snapshots=5)
    assert store.record_deploy_event({'event_type': 'unknown'}) is None


def test_build_lead_time_calcula_duracao():
    lead = build_lead_time(
        [
            {
                'deploy_key': 'd1',
                'event_type': 'deploy_started',
                'event_at': '2026-06-30T10:00:00+00:00',
            },
            {
                'deploy_key': 'd1',
                'event_type': 'deploy_finished',
                'event_at': '2026-06-30T10:05:00+00:00',
            },
        ]
    )
    assert lead['status'] == 'calculated'
    assert lead['value_seconds'] == 300.0
    assert lead['finished_deploys'] == 1


def test_durable_store_record_snapshot_e_lista(tmp_path):
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'snap.db'}", max_snapshots=5)
    recorded = store.record(
        {
            'correlation_id': 'corr-durable',
            'status': 'healthy',
            'risk_score': 5,
            'critical_counts': {},
            'evidence': {},
        }
    )
    snapshots = store.list_snapshots()
    assert snapshots[0]['correlation_id'] == recorded['correlation_id']
    assert store.storage_mode() == 'durable_sql'
    assert store.durable_storage_enabled() is True


def test_durable_store_record_deploy_event_persiste(tmp_path):
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'deploy2.db'}", max_snapshots=5)
    event = store.record_deploy_event(
        {
            'event_type': 'deploy_started',
            'deploy_key': 'deploy-x',
            'environment': 'dev',
            'correlation_id': 'corr-deploy',
        }
    )
    assert event is not None
    listed = store.list_deploy_events()
    assert listed[0]['deploy_key'] == 'deploy-x'


def test_build_mttr_ignora_eventos_sem_data():
    mttr = build_mttr(
        [
            {'incident_key': 'k', 'event_type': 'incident_opened', 'event_at': None},
            {'incident_key': 'k', 'event_type': 'incident_resolved', 'event_at': 'invalid'},
        ]
    )
    assert mttr['status'] == 'insufficient_resolved_incidents'


def test_build_lead_time_ignora_eventos_sem_data():
    lead = build_lead_time(
        [
            {'deploy_key': 'd', 'event_type': 'deploy_started', 'event_at': None},
        ]
    )
    assert lead['status'] == 'insufficient_deploy_events'


def test_build_runtime_topology_inclui_incidentes_e_ambientes(tmp_path):
    snapshot = {
        'correlation_id': 'corr-topology',
        'status': 'attention',
        'environment': 'dev',
        'service': 'reqsys-api',
    }
    incidents = [
        {'incident_key': 'runtime-health', 'event_type': 'incident_opened', 'correlation_id': 'corr-topology'},
    ]
    topology = build_runtime_topology(snapshot, [snapshot, {'environment': 'staging'}], incidents, [])

    assert topology['correlation_id'] == 'corr-topology'
    assert topology['coverage']['environment_dependencies'] == 2
    assert topology['coverage']['incident_relationships'] == 1
    assert topology['runtime_nodes'][0]['id'] == 'reqsys-api'


def test_build_correlation_report_relaciona_incidentes_e_deploys():
    snapshot = {'correlation_id': 'corr-rel', 'status': 'attention', 'risk_score': 5}
    incidents = [{'correlation_id': 'corr-rel', 'event_type': 'incident_opened'}]
    deploys = [{'correlation_id': 'corr-rel', 'event_type': 'deploy_started'}]
    report = build_correlation_report(snapshot, [snapshot], incidents, deploys)

    assert report['correlation_id'] == 'corr-rel'
    assert report['incident_correlation']['total_related_events'] == 1
    assert report['deploy_correlation']['total_related_events'] == 1


def test_build_observability_report_degraded_quando_status_critico():
    snapshot = {'correlation_id': 'corr-obs', 'status': 'degraded', 'risk_score': 85}
    topology = build_runtime_topology(snapshot, [snapshot], [], [])
    correlation = build_correlation_report(snapshot, [snapshot], [], [])
    report = build_observability_report(snapshot, {'failure_rate': 50}, topology, correlation)

    assert report['observability_percent'] < 100
    assert report['runtime_risk_scoring']['risk_classification'] == 'high'


def test_build_observability_report_baixo_risco():
    snapshot = {'correlation_id': 'corr-low', 'status': 'healthy', 'risk_score': 10}
    topology = build_runtime_topology(snapshot, [snapshot], [{'incident_key': 'k'}], [])
    correlation = build_correlation_report(snapshot, [snapshot], [], [])
    report = build_observability_report(snapshot, {'failure_rate': 0}, topology, correlation)

    assert report['runtime_risk_scoring']['risk_classification'] == 'low'
    assert report['incident_visibility'] == 100


def test_build_incident_event_reconhece_incidente_aberto():
    opened = {
        'status': 'degraded',
        'risk_score': 80,
        'critical_counts': {},
        'evidence': {'incident_key': 'svc-a'},
    }
    first = build_incident_event(opened, [])
    assert first is not None
    assert first['event_type'] == 'incident_opened'

    acknowledged = build_incident_event(
        {'status': 'blocked', 'risk_score': 90, 'critical_counts': {}, 'evidence': {'incident_key': 'svc-a'}},
        [first],
    )
    assert acknowledged is not None
    assert acknowledged['event_type'] == 'incident_acknowledged'


def test_durable_store_record_incident_event_persiste(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'incidents.db'}"
    store = DurableRuntimeAnalyticsStore(database_url=database_url, max_snapshots=5)
    snapshot = {
        'correlation_id': 'corr-inc',
        'status': 'degraded',
        'risk_score': 70,
        'critical_counts': {},
        'evidence': {'incident_key': 'api-gateway'},
    }
    event = store.record_incident_event(snapshot)
    assert event is not None
    assert store.list_incident_events()[0]['event_type'] == 'incident_opened'


def test_durable_store_record_deploy_event_rejeita_invalido(tmp_path):
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'deploy.db'}", max_snapshots=5)
    assert store.record_deploy_event({'event_type': 'unknown'}) is None


def test_build_runtime_analytics_com_store_vazio():
    from app.core.runtime_analytics import build_runtime_analytics

    store = RuntimeAnalyticsStore(max_snapshots=5)
    analytics = build_runtime_analytics(
        store,
        {
            'correlation_id': 'corr-empty',
            'status': 'healthy',
            'risk_score': 0,
            'critical_counts': {'pending_items': 0, 'blocked_items': 0, 'total_items': 0},
            'evidence': {},
        },
    )
    assert analytics['window']['total_snapshots'] == 1
    assert analytics['trends']['risk_score'] == 'insufficient_data'


def test_durable_store_engine_none_levanta_runtime_error(tmp_path):
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'engine.db'}", max_snapshots=5)
    store.engine = None
    with pytest.raises(RuntimeError, match='engine not initialized'):
        store.list_snapshots()
    store = DurableRuntimeAnalyticsStore(database_url=f"sqlite:///{tmp_path / 'engine.db'}", max_snapshots=5)
    store.engine = None
    with pytest.raises(RuntimeError, match='engine not initialized'):
        store.list_snapshots()
