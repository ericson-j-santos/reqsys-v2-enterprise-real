from fastapi.testclient import TestClient
import httpx

from app.main import app


def test_govbi_perguntas_usa_analitico_local_quando_externo_falha(monkeypatch, db_session):
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
                json={'erro': 'REQUISICAO_INVALIDA', 'mensagem': 'metrica invalida'},
            )
            raise httpx.HTTPStatusError('bad request', request=request, response=response)

    import app.api.govbi as govbi

    monkeypatch.setattr(govbi.httpx, 'AsyncClient', ClientComErroNegocio)

    client = TestClient(app)
    response = client.post(
        '/api/govbi/perguntas',
        json={
            'pergunta': 'Total por situação aprovada vs reprovada',
            'formatoResposta': 'tabela',
            'exibirSql': True,
        },
        headers={'X-Correlation-Id': 'test-local-analytics'},
    )

    assert response.status_code == 200
    data = response.json()
    assert data['statusFluxo'] == 'CONCLUIDO'
    assert data['fonteAnalitica'] == 'reqsys-sqlite'
    assert data['resultado']['colunas'] == ['status', 'quantidade']
    assert len(data['resultado']['linhas']) >= 1


def test_govbi_health_expoe_analitico_local():
    client = TestClient(app)
    response = client.get('/api/govbi/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['analitico_local']['disponivel'] is True
    assert payload['data']['analitico_local']['fonte'] == 'reqsys-sqlite'
