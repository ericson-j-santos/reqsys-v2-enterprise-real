from fastapi.testclient import TestClient

from app.api.monitoramento_operacional import ItemMonitorado, classificar_estado_geral
from app.main import app


def test_monitoramento_operacional_retorna_envelope_e_contrato_minimo():
    correlation_id = 'test-correlation-monitoramento'
    res = TestClient(app).get('/monitoramento-operacional', headers={'X-Correlation-Id': correlation_id})

    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['correlation_id'] == correlation_id

    data = body['data']
    assert data['schema_version'] == '1.0.0'
    assert data['correlation_id'] == correlation_id
    assert data['ambiente'] == 'dev'
    assert data['resumo']['estado_geral'] in {'verde', 'amarelo', 'vermelho', 'bloqueado', 'desconhecido'}
    assert data['resumo']['total_itens'] == len(data['itens'])
    assert data['itens']


def test_monitoramento_operacional_nao_expoe_campos_sensiveis():
    res = TestClient(app).get('/monitoramento-operacional')
    payload = str(res.json()).lower()

    termos_proibidos = ['token', 'password', 'senha', 'secret', 'connection string', 'cpf']
    for termo in termos_proibidos:
        assert termo not in payload


def test_classificador_prioriza_bloqueio():
    itens = [
        ItemMonitorado(
            tipo='workflow',
            referencia='ci',
            titulo='CI',
            estado='verde',
            severidade='baixa',
            origem='teste',
        ),
        ItemMonitorado(
            tipo='gate',
            referencia='prod',
            titulo='Gate de producao',
            estado='bloqueado',
            severidade='critica',
            origem='teste',
            bloqueante=True,
        ),
    ]

    assert classificar_estado_geral(itens) == 'bloqueado'


def test_classificador_sem_itens_retorna_desconhecido():
    assert classificar_estado_geral([]) == 'desconhecido'
