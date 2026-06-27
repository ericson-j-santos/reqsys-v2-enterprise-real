"""Testes para o middleware global de Correlation ID."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_correlation_id_gerado_automaticamente():
    """Sem header X-Correlation-Id, o middleware deve gerar um UUID e devolvê-lo na resposta."""
    resp = client.get('/health')
    assert resp.status_code == 200
    correlation_id = resp.headers.get('x-correlation-id')
    assert correlation_id is not None, 'Header X-Correlation-Id ausente na resposta'
    assert re.match(r'^[0-9a-f-]{36}$', correlation_id), f'Correlation ID não é UUID v4: {correlation_id!r}'


def test_correlation_id_propagado_do_request():
    """Se X-Correlation-Id for enviado, deve ser devolvido no response sem alteração."""
    enviado = 'teste-correlacao-12345'
    resp = client.get('/health', headers={'X-Correlation-Id': enviado})
    assert resp.status_code == 200
    devolvido = resp.headers.get('x-correlation-id')
    assert devolvido == enviado, f'Correlation ID não propagado: esperado {enviado!r}, recebido {devolvido!r}'


def test_correlation_id_x_request_id_como_fallback():
    """X-Request-ID deve ser aceito como fallback quando X-Correlation-Id não for enviado."""
    request_id = 'request-id-fallback-999'
    resp = client.get('/health', headers={'X-Request-ID': request_id})
    assert resp.status_code == 200
    correlation_id = resp.headers.get('x-correlation-id')
    assert correlation_id == request_id, f'X-Request-ID não usado como fallback: {correlation_id!r}'


def test_correlation_id_em_rota_runtime():
    """O middleware deve injetar Correlation ID em qualquer rota, incluindo /api/runtime/health."""
    resp = client.get('/api/runtime/health')
    assert resp.status_code == 200
    assert resp.headers.get('x-correlation-id') is not None


def test_correlation_id_em_rota_raiz():
    """O middleware deve injetar Correlation ID na rota /."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert resp.headers.get('x-correlation-id') is not None


def test_correlation_ids_distintos_por_request():
    """Cada request sem header deve receber um Correlation ID distinto."""
    r1 = client.get('/health')
    r2 = client.get('/health')
    cid1 = r1.headers.get('x-correlation-id')
    cid2 = r2.headers.get('x-correlation-id')
    assert cid1 is not None
    assert cid2 is not None
    assert cid1 != cid2, 'Dois requests distintos não devem compartilhar o mesmo Correlation ID automático'
