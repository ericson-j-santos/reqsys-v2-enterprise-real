from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import GovBIConfigurationError, validate_govbi_base_url
from app.main import app


@pytest.fixture(autouse=True)
def _govbi_base_url_aprovada(monkeypatch):
    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.settings, 'govbi_base_url', 'https://govbi.example')


def test_govbi_perguntas_retorna_erro_negocio_quando_servico_externo_rejeita(monkeypatch):
    class ClientComErroNegocio:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            response = httpx.Response(
                400,
                request=request,
                json={
                    'erro': 'REQUISICAO_INVALIDA',
                    'mensagem': 'Métrica não encontrada no catálogo semântico: exemplo',
                },
            )
            raise httpx.HTTPStatusError('bad request', request=request, response=response)

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientComErroNegocio)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={
            'pergunta': 'Consulta com métrica inválida',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
        headers={'X-Correlation-Id': 'test-erro-negocio'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['statusFluxo'] == 'ERRO'
    assert data['correlationId'] == 'test-erro-negocio'
    assert 'catálogo semântico' in data['avisos'][0]


def test_govbi_perguntas_retorna_fallback_governado_quando_servico_externo_falha(monkeypatch):
    class ClientComFalha:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError('falha simulada')

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientComFalha)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={
            'pergunta': 'Quantas propostas por mês em 2024?',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
        headers={'X-Correlation-Id': 'test-correlation-id'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['statusFluxo'] == 'MODO_DEGRADADO'
    assert data['correlationId'] == 'test-correlation-id'
    assert data['resultado']['colunas'] == ['item', 'valor', 'status']
    assert data['mascaramentoAplicado'] is True


def test_govbi_perguntas_valida_payload_minimo():
    client = TestClient(app)
    response = client.post('/api/govbi/perguntas', json={'pergunta': 'oi'})

    assert response.status_code == 422


def test_govbi_health_retorna_envelope_operacional():
    client = TestClient(app)
    response = client.get('/api/govbi/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['data']['service'] == 'govbi-proxy'
    assert payload['data']['status'] == 'ok'


def test_govbi_funcionamento_retorna_cem_por_cento():
    client = TestClient(app)
    response = client.get('/api/govbi/funcionamento')

    assert response.status_code == 200
    payload = response.json()
    dados = payload['data']
    assert dados['completo'] is True
    assert dados['percentual'] == 100
    assert dados['aprovados'] == dados['total']
    assert len(dados['resultados']) >= 5


def test_govbi_perguntas_normaliza_resposta_externa_com_sucesso(monkeypatch):
    class ClientComSucesso:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            return httpx.Response(
                200,
                request=request,
                json={
                    'statusFluxo': 'CONCLUIDO',
                    'resultado': {'colunas': ['total'], 'linhas': [{'total': 10}]},
                    'sqlGerado': 'SELECT 1',
                },
            )

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientComSucesso)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Quantas propostas por mês?', 'formatoResposta': 'tabela', 'exibirSql': True},
        headers={'X-Correlation-Id': 'corr-govbi-ok'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['statusFluxo'] == 'CONCLUIDO'
    assert data['correlationId'] == 'corr-govbi-ok'
    assert data['resultado']['colunas'] == ['total']


def test_govbi_perguntas_http_400_sem_json_cai_em_fallback(monkeypatch):
    class ClientCom400SemJson:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            response = httpx.Response(400, request=request, content=b'corpo-invalido')
            raise httpx.HTTPStatusError('bad request', request=request, response=response)

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientCom400SemJson)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Consulta com resposta inválida', 'formatoResposta': 'tabela', 'exibirSql': True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['statusFluxo'] == 'MODO_DEGRADADO'
    assert 'HTTP 400' in data['resultado']['linhas'][1]['valor']


def test_govbi_perguntas_resposta_nao_dict_cai_em_fallback(monkeypatch):
    class ClientComJsonLista:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi.example/api/v1/perguntas')
            return httpx.Response(200, request=request, json=['nao', 'dict'])

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientComJsonLista)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={'pergunta': 'Resposta inválida do serviço', 'formatoResposta': 'tabela', 'exibirSql': True},
    )

    assert response.status_code == 200
    assert response.json()['statusFluxo'] == 'MODO_DEGRADADO'


@pytest.mark.parametrize(
    'base_url',
    [
        'https://fly.dev',
        'https://govbi.fly.dev',
        'https://fly.io',
        'https://govbi.fly.io',
    ],
)
def test_validacao_govbi_rejeita_hosts_fly(base_url):
    with pytest.raises(GovBIConfigurationError, match='não pode apontar'):
        validate_govbi_base_url(base_url)


def test_govbi_perguntas_sem_url_explicita_retorna_503(monkeypatch):
    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.settings, 'govbi_base_url', '')
    with patch.object(govbi.httpx, 'AsyncClient') as async_client:
        response = TestClient(app).post(
            '/api/govbi/perguntas',
            json={'pergunta': 'Consulta sem configuração'},
        )

    assert response.status_code == 503
    assert response.json()['detail'] == 'Integração GovBI indisponível.'
    assert 'GOVBI_BASE_URL' not in response.text
    async_client.assert_not_called()


def test_govbi_health_reporta_bloqueio_para_host_fly(monkeypatch):
    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.settings, 'govbi_base_url', 'https://govbi.fly.dev')
    response = TestClient(app).get('/api/govbi/health')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'bloqueado'
    assert data['external_base_url_configured'] is False
    assert data['configuration_error'] == 'GOVBI_BASE_URL não pode apontar para Fly.io ou fly.dev.'
