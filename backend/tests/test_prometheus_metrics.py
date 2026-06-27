"""Testes para o endpoint de métricas Prometheus expandido."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_METRICS = [
    'reqsys_runtime_up',
    'reqsys_runtime_status',
    'reqsys_runtime_ready',
    'reqsys_runtime_risk_score',
    'reqsys_runtime_pending_items',
    'reqsys_runtime_blocked_items',
    'reqsys_runtime_total_items',
    'reqsys_runtime_uptime_seconds',
    'reqsys_security_demo_login_enabled',
    'reqsys_security_jwt_secret_weak',
    'reqsys_security_cors_wildcard',
    'reqsys_security_production_gates_ok',
]


def test_metrics_endpoint_retorna_200():
    resp = client.get('/api/runtime/metrics')
    assert resp.status_code == 200


def test_metrics_content_type_prometheus():
    resp = client.get('/api/runtime/metrics')
    assert 'text/plain' in resp.headers.get('content-type', '')


def test_metrics_contem_todas_metricas_esperadas():
    resp = client.get('/api/runtime/metrics')
    corpo = resp.text
    faltando = [m for m in EXPECTED_METRICS if m not in corpo]
    assert not faltando, f'Métricas ausentes no endpoint: {faltando}'


def test_metrics_formato_prometheus():
    """Cada métrica deve ter linha HELP e TYPE antes do valor."""
    resp = client.get('/api/runtime/metrics')
    linhas = resp.text.splitlines()
    help_lines = [l for l in linhas if l.startswith('# HELP')]
    type_lines = [l for l in linhas if l.startswith('# TYPE')]
    assert len(help_lines) >= len(EXPECTED_METRICS)
    assert len(type_lines) >= len(EXPECTED_METRICS)


def test_metrics_runtime_up_vale_1():
    resp = client.get('/api/runtime/metrics')
    linhas = resp.text.splitlines()
    for linha in linhas:
        if linha.startswith('reqsys_runtime_up{'):
            assert linha.endswith(' 1'), f'reqsys_runtime_up esperado 1, recebido: {linha!r}'
            return
    pytest.fail('Métrica reqsys_runtime_up não encontrada no corpo da resposta')


def test_metrics_security_valores_binarios():
    """Métricas de segurança devem ser 0 ou 1."""
    resp = client.get('/api/runtime/metrics')
    linhas = resp.text.splitlines()
    security_metrics = [
        'reqsys_security_demo_login_enabled',
        'reqsys_security_jwt_secret_weak',
        'reqsys_security_cors_wildcard',
        'reqsys_security_production_gates_ok',
    ]
    for metrica in security_metrics:
        for linha in linhas:
            if linha.startswith(f'{metrica}{{') or linha.startswith(f'{metrica} '):
                valor = linha.split()[-1]
                assert valor in {'0', '1'}, f'{metrica} deve ser 0 ou 1, recebido: {valor!r}'
                break
