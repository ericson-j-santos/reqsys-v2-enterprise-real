import httpx

import app.api.govbi as govbi_api


class _FakeResponseSuccess:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClientSuccess:
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get('timeout')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        assert url.endswith('/api/v1/perguntas')
        assert json['pergunta'] == 'Quantas propostas por mês em 2024?'
        assert headers['X-Correlation-Id'] == 'corr-govbi-test-001'
        return _FakeResponseSuccess({
            'avisos': [],
            'nivelSensibilidade': 'BAIXA',
            'statusFluxo': 'CONCLUIDO',
            'metrica': 'contagem_registros',
            'dimensoes': ['mes'],
            'filtros': {'ano': '2024'},
            'correlationId': headers['X-Correlation-Id'],
            'sqlGerado': 'SELECT mes, COUNT(*) AS total FROM propostas GROUP BY mes',
            'resultado': {
                'colunas': ['mes', 'total'],
                'linhas': [{'mes': '2024-01', 'total': 10}],
            },
            'mascaramentoAplicado': False,
            'requerAprovacao': False,
            'explicacao': 'mock externo',
        })


class _FakeAsyncClientTimeout:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.TimeoutException('timeout controlado no teste')


def test_govbi_status_requer_autenticacao(client):
    resp = client.get('/govbi/status')

    assert resp.status_code == 401


def test_govbi_status_autenticado(client, auth_headers):
    resp = client.get('/govbi/status', headers=auth_headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'ok'
    assert payload['data']['modo'] == 'proxy_governado'
    assert payload['data']['timeout_ms'] >= 1000


def test_govbi_perguntas_normaliza_resposta_externa(client, auth_headers, monkeypatch):
    monkeypatch.setattr(govbi_api.httpx, 'AsyncClient', _FakeAsyncClientSuccess)

    resp = client.post(
        '/govbi/perguntas',
        headers={**auth_headers, 'X-Correlation-Id': 'corr-govbi-test-001'},
        json={
            'pergunta': 'Quantas propostas por mês em 2024?',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    assert payload['meta']['correlation_id'] == 'corr-govbi-test-001'
    assert payload['data']['statusFluxo'] == 'CONCLUIDO'
    assert payload['data']['origem'] == 'govbi_externo'
    assert payload['data']['resultado']['colunas'] == ['mes', 'total']
    assert payload['data']['correlationId'] == 'corr-govbi-test-001'


def test_govbi_perguntas_retorna_fallback_governado_quando_provider_falha(client, auth_headers, monkeypatch):
    monkeypatch.setattr(govbi_api.httpx, 'AsyncClient', _FakeAsyncClientTimeout)

    resp = client.post(
        '/govbi/perguntas',
        headers={**auth_headers, 'X-Correlation-Id': 'corr-govbi-test-001'},
        json={
            'pergunta': 'Propostas por unidade no último trimestre',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['success'] is True
    assert payload['meta']['correlation_id'] == 'corr-govbi-test-001'
    assert payload['data']['statusFluxo'] == 'MODO_DEGRADADO'
    assert payload['data']['origem'] == 'fallback_backend_reqsys'
    assert payload['data']['resultado']['colunas'] == ['item', 'valor', 'status']
    assert payload['data']['correlationId'] == 'corr-govbi-test-001'


def test_govbi_perguntas_payload_invalido_retorna_422(client, auth_headers):
    resp = client.post('/govbi/perguntas', headers=auth_headers, json={'pergunta': ''})

    assert resp.status_code == 422
