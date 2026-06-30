from fastapi.testclient import TestClient

from app.api.monitoramento_operacional import _metric_line
from app.schemas.monitoramento_operacional import ItemMonitorado
from app.services.monitoramento_snapshot import classificar_estado_geral
from app.core.config import settings
from app.main import app


def test_monitoramento_operacional_status_200():
    res = TestClient(app).get('/monitoramento-operacional')
    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['data']['schema_version'] == '1.0.0'
    assert body['data']['resumo']['total_itens'] == len(body['data']['itens'])


def test_monitoramento_operacional_propaga_correlation_id():
    correlation_id = 'corr-oper-005-test'
    res = TestClient(app).get('/monitoramento-operacional', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    body = res.json()
    assert body['meta']['correlation_id'] == correlation_id
    assert body['data']['correlation_id'] == correlation_id


def test_monitoramento_operacional_expoe_frentes_operacionais_prioritarias():
    res = TestClient(app).get('/monitoramento-operacional')
    referencias = {item['referencia'] for item in res.json()['data']['itens']}

    assert {'REQSYS-OPER-001', 'REQSYS-OPER-002', 'REQSYS-OPER-003', 'REQSYS-OPER-004', 'REQSYS-OPER-005'} <= referencias


def test_monitoramento_operacional_estado_geral_reflete_pendencias():
    res = TestClient(app).get('/monitoramento-operacional')
    data = res.json()['data']

    assert data['resumo']['estado_geral'] in {'amarelo', 'vermelho', 'bloqueado'}
    assert data['resumo']['pendencias'] > 0


def test_monitoramento_operacional_expoe_modo_coleta():
    res = TestClient(app).get('/monitoramento-operacional')
    data = res.json()['data']

    assert data['modo_coleta'] in {'live', 'hibrido', 'preview'}
    assert isinstance(data.get('coleta_detalhes'), dict)


def test_runtime_observability_health_expoe_snapshot_governado():
    correlation_id = 'corr-runtime-observability-test'
    res = TestClient(app).get('/api/runtime/health', headers={'X-Correlation-ID': correlation_id})

    assert res.status_code == 200
    body = res.json()
    data = body['data']

    assert body['success'] is True
    assert body['meta']['correlation_id'] == correlation_id
    assert data['correlation_id'] == correlation_id
    assert data['schema_version'] == '1.0.0'
    assert data['service'] == 'reqsys-api'
    assert data['status'] in {'healthy', 'attention', 'degraded'}
    assert 0 <= data['risk_score'] <= 100
    assert data['uptime_seconds'] >= 0
    assert data['evidence']['no_secrets'] is True
    if settings.is_production:
        assert data['evidence']['deploy_gate_relaxed'] is False
    else:
        assert data['evidence']['deploy_gate_relaxed'] is True
        assert data['status'] == 'healthy'
        assert data['status_raw'] in {'attention', 'degraded'}


def test_runtime_dashboard_schema_expoe_cards_e_drilldowns():
    correlation_id = 'corr-runtime-dashboard-schema-test'
    res = TestClient(app).get('/api/runtime/dashboard', headers={'X-Correlation-ID': correlation_id})

    assert res.status_code == 200
    body = res.json()
    data = body['data']
    card_ids = {card['id'] for card in data['cards']}
    section_ids = {section['id'] for section in data['sections']}

    assert body['meta']['correlation_id'] == correlation_id
    assert data['schema_version'] == '1.3.0'
    assert data['correlation_id'] == correlation_id
    assert data['layout']['responsive'] is True
    assert data['data_source']['endpoint'] == '/api/runtime/health'
    assert {'runtime-status', 'risk-score', 'pending-items', 'uptime', 'readiness-percent', 'fly-duckdns-status', 'governance-evidence-score', 'trilha-d-score'} <= card_ids
    assert any(card['id'].startswith('governance-') for card in data['cards'])
    assert any(card['id'].startswith('trilha-d-dim-') for card in data['cards'])
    assert {'workflow-topology', 'public-smoke', 'operational-timeline', 'environment-evidence', 'incident-summary', 'risk-summary', 'environment-drift-summary', 'governance-evidence', 'trilha-d-history'} <= section_ids
    governance = next(section for section in data['sections'] if section['id'] == 'governance-evidence')
    assert governance['type'] == 'governance_cards'
    assert governance['items']['evidence']
    assert data['governance_evidence']['summary']['total_capabilities'] >= 4
    trilha_d = next(section for section in data['sections'] if section['id'] == 'trilha-d-history')
    assert trilha_d['type'] == 'trilha_d_history'
    assert trilha_d['items']['history']
    assert data['trilha_d_history']['dimension_summary']
    topology = next(section for section in data['sections'] if section['id'] == 'workflow-topology')
    assert topology['type'] == 'timeline'
    assert {item['step'] for item in topology['items']} == {'health', 'readiness', 'metrics', 'monitoring'}
    assert data['guardrails']['no_secrets'] is True
    assert data['guardrails']['read_only'] is True
    assert data['guardrails']['deploy_gate_relaxed'] is (not settings.is_production)
    runtime_card = next(card for card in data['cards'] if card['id'] == 'runtime-status')
    assert runtime_card['spa_drilldown']['path'] == '/monitoramento-operacional'
    assert runtime_card['spa_drilldown']['query']['secao'] == 'runtime'


def test_runtime_observability_readiness_e_liveness():
    client = TestClient(app)

    readiness = client.get('/api/runtime/readiness')
    liveness = client.get('/api/runtime/liveness')

    assert readiness.status_code == 200
    assert liveness.status_code == 200
    if settings.is_production:
        assert readiness.json()['data']['ready'] is False
        assert readiness.json()['data']['readiness_reason'] == 'runtime_degraded'
    else:
        assert readiness.json()['data']['ready'] is True
        assert readiness.json()['data']['readiness_reason'] == 'runtime_healthy'
        assert readiness.json()['data']['evidence']['deploy_gate_relaxed'] is True
    assert liveness.json()['data']['alive'] is True


def test_runtime_observability_readiness_strict_em_producao(monkeypatch):
    monkeypatch.setattr(settings, 'app_environment', 'production')
    client = TestClient(app)

    readiness = client.get('/api/runtime/readiness')
    data = readiness.json()['data']

    assert readiness.status_code == 200
    assert data['evidence']['deploy_gate_relaxed'] is False
    assert data['ready'] is False
    assert data['readiness_reason'] == 'runtime_degraded'
    assert data['status'] == 'degraded'


def test_runtime_observability_metrics_prometheus_text_plain():
    res = TestClient(app).get('/api/runtime/metrics')

    assert res.status_code == 200
    assert res.headers['content-type'].startswith('text/plain')
    text = res.text
    assert 'reqsys_runtime_up' in text
    assert 'reqsys_runtime_risk_score' in text
    assert 'reqsys_runtime_pending_items' in text
    assert 'reqsys_runtime_blocked_items' in text
    assert 'reqsys_runtime_uptime_seconds' in text
    assert '<script' not in text.lower()


def test_runtime_observability_metric_line_escapa_labels_prometheus():
    unsafe_environment = 'prod"' + chr(10) + 'unsafe'
    line = _metric_line('reqsys_runtime_up', 1, {'environment': unsafe_environment, 'service': 'reqsys\\api'})

    assert 'environment="prod\\"\\nunsafe"' in line
    assert 'service="reqsys\\\\api"' in line
    assert chr(10) not in line


def test_classificar_estado_geral_prioriza_bloqueio():
    itens = [
        ItemMonitorado(tipo='gate', referencia='ok', titulo='OK', estado='verde', severidade='baixa', origem='teste'),
        ItemMonitorado(tipo='pr', referencia='bloq', titulo='Bloqueado', estado='verde', severidade='critica', origem='teste', bloqueante=True),
    ]

    assert classificar_estado_geral(itens) == 'bloqueado'


def test_classificar_estado_geral_sem_itens_desconhecido():
    assert classificar_estado_geral([]) == 'desconhecido'
