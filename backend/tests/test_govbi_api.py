from fastapi.testclient import TestClient
import httpx

from app.main import app


def test_govbi_perguntas_retorna_erro_negocio_quando_servico_externo_rejeita(monkeypatch):
    class ClientComErroNegocio:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request('POST', 'https://govbi-ia-hom.fly.dev/api/v1/perguntas')
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
    import httpx as httpx_module

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
