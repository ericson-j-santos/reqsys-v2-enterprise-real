"""Testes da Trilha B — Observabilidade Enterprise."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.core.correlation import definir_correlation_id, extrair_correlation_id_dos_headers, resolver_correlation_id
from app.core.feature_metrics import REGISTRY, identificar_feature
from app.core.otel import configurar_opentelemetry, otel_ativo
from app.main import app


def test_extrair_correlation_id_dos_headers_prioriza_correlation():
    headers = {'X-Correlation-Id': 'corr-abc', 'X-Request-ID': 'req-xyz'}
    assert extrair_correlation_id_dos_headers(headers) == 'corr-abc'


def test_definir_correlation_id_normaliza_entrada_direta():
    assert definir_correlation_id('  corr-direto  ') == 'corr-direto'
    assert resolver_correlation_id() == 'corr-direto'


def test_definir_correlation_id_em_branco_gera_novo_id():
    valor = definir_correlation_id('   ')

    assert str(UUID(valor)) == valor
    assert resolver_correlation_id() == valor


def test_definir_correlation_id_nulo_gera_novo_id():
    valor = definir_correlation_id(None)

    assert str(UUID(valor)) == valor
    assert resolver_correlation_id() == valor


def test_resolver_correlation_id_usa_request_id_como_fallback():
    definir_correlation_id('anterior')
    assert resolver_correlation_id(None, 'req-fallback') == 'req-fallback'


def test_identificar_feature_mapeia_rotas_conhecidas():
    assert identificar_feature('/api/requisitos/1') == 'requisitos'
    assert identificar_feature('/govbi/consulta') == 'govbi'
    assert identificar_feature('/health') == 'core'


def test_middleware_propaga_correlation_id_na_resposta():
    client = TestClient(app)
    correlation_id = 'corr-middleware-enterprise'

    res = client.get('/health', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    assert res.headers.get('X-Correlation-Id') == correlation_id
    assert res.json()['meta']['correlation_id'] == correlation_id


def test_middleware_sem_header_gera_e_propaga_mesmo_correlation_id():
    client = TestClient(app)

    res = client.get('/health')

    assert res.status_code == 200
    correlation_id = res.headers.get('X-Correlation-Id')
    assert correlation_id
    assert res.json()['meta']['correlation_id'] == correlation_id


def test_middleware_registra_metricas_por_feature():
    client = TestClient(app)
    client.get('/health')
    client.get('/api/runtime/liveness')

    features = {item.feature for item in REGISTRY.snapshot()}
    assert 'core' in features
    assert 'runtime' in features


def test_runtime_metrics_expoe_metricas_por_feature():
    client = TestClient(app)
    client.get('/health')
    client.get('/api/runtime/metrics')

    res = client.get('/api/runtime/metrics')
    text = res.text

    assert 'reqsys_http_requests_total' in text
    assert 'feature="' in text


def test_runtime_analytics_expoe_operational_telemetry():
    client = TestClient(app)
    correlation_id = 'corr-analytics-telemetry'

    res = client.get('/api/runtime/analytics', headers={'X-Correlation-ID': correlation_id})
    body = res.json()

    assert res.status_code == 200
    telemetry = body['data']['operational_telemetry']
    assert telemetry['correlation_id'] == correlation_id
    assert telemetry['distributed_tracing']['correlation_propagation'] == 'x-correlation-id'
    assert 'feature_metrics' in telemetry
    assert telemetry['feature_metrics']['schema_version'] == '1.0.0'


def test_opentelemetry_desabilitado_por_padrao():
    assert otel_ativo() is False
    configurar_opentelemetry(app)
    assert otel_ativo() is False
