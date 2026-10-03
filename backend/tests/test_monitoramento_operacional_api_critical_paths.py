"""Caminhos críticos — API monitoramento operacional e métricas runtime."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.monitoramento_operacional import (
    _metric_line,
    _runtime_risk_score,
    _runtime_status,
)
from app.core.feature_metrics import REGISTRY
from app.main import app
from app.schemas.monitoramento_operacional import ItemMonitorado, MonitoramentoOperacional, ResumoMonitoramento

client = TestClient(app)


def test_runtime_status_mapeia_estados():
    assert _runtime_status('bloqueado') == 'degraded'
    assert _runtime_status('vermelho') == 'degraded'
    assert _runtime_status('amarelo') == 'attention'
    assert _runtime_status('desconhecido') == 'attention'
    assert _runtime_status('verde') == 'healthy'


def test_runtime_risk_score_com_lista_vazia():
    snapshot = MonitoramentoOperacional(
        correlation_id='corr-risk',
        coletado_em='2026-06-30T00:00:00Z',
        ambiente='test',
        modo_coleta='preview',
        resumo=ResumoMonitoramento(
            total_itens=0,
            pendencias=0,
            bloqueios=0,
            estado_geral='desconhecido',
        ),
        itens=[],
    )
    assert _runtime_risk_score(snapshot) == 50


def test_runtime_risk_score_pondera_severidade():
    snapshot = MonitoramentoOperacional(
        correlation_id='corr-risk-2',
        coletado_em='2026-06-30T00:00:00Z',
        ambiente='test',
        modo_coleta='preview',
        resumo=ResumoMonitoramento(
            total_itens=2,
            pendencias=1,
            bloqueios=1,
            estado_geral='vermelho',
        ),
        itens=[
            ItemMonitorado(
                tipo='a',
                referencia='1',
                titulo='critico',
                estado='vermelho',
                severidade='critica',
                origem='teste',
                bloqueante=True,
            ),
            ItemMonitorado(
                tipo='b',
                referencia='2',
                titulo='ok',
                estado='verde',
                severidade='baixa',
                origem='teste',
            ),
        ],
    )
    assert _runtime_risk_score(snapshot) > 0


def test_metric_line_com_labels_escapa_caracteres():
    line = _metric_line('reqsys_test', 1, {'env': 'dev\n', 'svc': 'api"1'})
    assert 'reqsys_test{' in line
    assert '\\n' in line
    assert '\\"' in line


def test_metric_line_sem_labels():
    assert _metric_line('reqsys_up', 1) == 'reqsys_up 1'


@patch.object(REGISTRY, 'snapshot', return_value=[])
def test_runtime_metrics_retorna_prometheus(_snapshot):
    response = client.get('/api/runtime/metrics', headers={'X-Correlation-ID': 'corr-metrics'})
    assert response.status_code == 200
    assert 'reqsys_runtime_up' in response.text
    assert 'reqsys_runtime_risk_score' in response.text


@patch.object(
    REGISTRY,
    'snapshot',
    return_value=[
        type('Item', (), {'feature': 'govbi', 'requests_total': 3, 'errors_total': 1, 'duration_ms_total': 120})(),
    ],
)
def test_runtime_metrics_inclui_feature_counters(_snapshot):
    response = client.get('/api/runtime/metrics')
    assert response.status_code == 200
    assert 'reqsys_http_requests_total' in response.text
    assert 'reqsys_http_errors_total' in response.text
    assert 'reqsys_http_duration_ms_total' in response.text
    assert 'feature="govbi"' in response.text


def test_operacao_autonoma_maturidade_endpoint():
    response = client.get('/operacao-autonoma/maturidade', headers={'X-Correlation-ID': 'corr-mat'})
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == 'corr-mat'


def test_operacao_autonoma_runtime_health_endpoint():
    response = client.get('/operacao-autonoma/runtime-health', headers={'X-Correlation-ID': 'corr-health'})
    assert response.status_code == 200
    data = response.json()['data']
    assert data['correlation_id'] == 'corr-health'
    assert data['componentes']


def test_runtime_operational_mesh_endpoint():
    response = client.get('/api/runtime/operational-mesh', headers={'X-Correlation-ID': 'corr-mesh'})
    assert response.status_code == 200
    data = response.json()['data']
    assert data['correlation_id'] == 'corr-mesh'


def test_runtime_dashboard_expoe_merge_readiness_history():
    response = client.get('/api/runtime/dashboard')
    assert response.status_code == 200
    body = response.json()['data']
    section_ids = [section['id'] for section in body.get('sections') or []]
    card_ids = [card['id'] for card in body.get('cards') or []]
    assert 'merge-readiness-history' in section_ids
    assert 'merge-readiness-history' in card_ids
    assert body.get('merge_readiness_history', {}).get('summary')


def test_runtime_dashboard_expoe_continuous_trilha_d_monitoring_history():
    response = client.get('/api/runtime/dashboard')
    assert response.status_code == 200
    body = response.json()['data']
    section_ids = [section['id'] for section in body.get('sections') or []]
    card_ids = [card['id'] for card in body.get('cards') or []]
    assert 'continuous-trilha-d-monitoring-history' in section_ids
    assert 'continuous-trilha-d-monitoring-history' in card_ids
    assert body.get('continuous_trilha_d_monitoring_history', {}).get('summary')
