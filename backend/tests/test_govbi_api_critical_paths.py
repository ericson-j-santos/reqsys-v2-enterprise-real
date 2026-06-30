"""Caminhos críticos — API GovBI (health, funcionamento e proxy)."""

from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi.testclient import TestClient

from app.api.govbi import _correlation_id, _normalizar_resposta
from app.main import app


def test_correlation_id_gera_quando_ausente():
    generated = _correlation_id(None)
    assert generated.startswith('govbi-')


def test_correlation_id_preserva_header():
    assert _correlation_id('  corr-govbi-001  ') == 'corr-govbi-001'


def test_normalizar_resposta_preenche_campos_canonicos():
    data = _normalizar_resposta(
        {
            'resultado': {'colunas': ['a'], 'linhas': [{'a': 1}]},
            'statusFluxo': 'CONCLUIDO',
            'correlationId': 'ext-1',
        },
        'corr-local',
    )
    assert data['statusFluxo'] == 'CONCLUIDO'
    assert data['correlationId'] == 'ext-1'
    assert data['resultado']['colunas'] == ['a']
    assert data['mascaramentoAplicado'] is True


def test_govbi_health_endpoint():
    client = TestClient(app)
    response = client.get('/api/govbi/health')
    assert response.status_code == 200
    data = response.json()['data']
    assert data['service'] == 'govbi-proxy'
    assert data['status'] == 'ok'
    assert data['timeout_seconds'] > 0


def test_govbi_funcionamento_endpoint():
    client = TestClient(app)
    response = client.get('/api/govbi/funcionamento')
    assert response.status_code == 200
    data = response.json()['data']
    assert data['total'] >= 5
    assert data['percentual'] >= 0
    assert len(data['resultados']) == data['total']


def test_erro_negocio_govbi_normaliza_mensagem():
    from app.api.govbi import _erro_negocio_govbi

    payload = _erro_negocio_govbi('pergunta teste', 'corr-err', {'mensagem': 'metrica invalida'})
    assert payload['statusFluxo'] == 'ERRO'
    assert payload['correlationId'] == 'corr-err'
    assert 'metrica invalida' in payload['avisos'][0]


def test_govbi_perguntas_http_500_retorna_fallback(monkeypatch):
    class ClientHttpError:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError('server error', request=request, response=response)

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientHttpError)
    client = TestClient(app)

    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Consulta com falha HTTP', 'formatoResposta': 'tabela'},
    )
    assert response.status_code == 200
    assert response.json()['statusFluxo'] == 'MODO_DEGRADADO'


def test_govbi_perguntas_http_400_sem_payload_json_cai_em_fallback(monkeypatch):
    class ClientBadJson:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            response = httpx.Response(400, request=request, text='not-json')
            raise httpx.HTTPStatusError('bad request', request=request, response=response)

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientBadJson)
    client = TestClient(app)

    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Consulta com erro 400', 'formatoResposta': 'tabela'},
    )
    assert response.status_code == 200
    assert response.json()['statusFluxo'] == 'MODO_DEGRADADO'


def test_govbi_perguntas_resposta_nao_dict_cai_em_fallback(monkeypatch):
    class ClientLista:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = ['invalido']
            return mock_response

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientLista)
    client = TestClient(app)

    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Resposta invalida', 'formatoResposta': 'tabela'},
    )
    assert response.status_code == 200
    assert response.json()['statusFluxo'] == 'MODO_DEGRADADO'
