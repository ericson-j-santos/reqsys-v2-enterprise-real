from fastapi.testclient import TestClient

from app.api.monitoramento_operacional import ItemMonitorado, classificar_estado_geral
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


def test_classificar_estado_geral_prioriza_bloqueio():
    itens = [
        ItemMonitorado(tipo='gate', referencia='ok', titulo='OK', estado='verde', severidade='baixa', origem='teste'),
        ItemMonitorado(tipo='pr', referencia='bloq', titulo='Bloqueado', estado='verde', severidade='critica', origem='teste', bloqueante=True),
    ]

    assert classificar_estado_geral(itens) == 'bloqueado'


def test_classificar_estado_geral_sem_itens_desconhecido():
    assert classificar_estado_geral([]) == 'desconhecido'


def test_snapshot_nao_marca_draft_como_pronto_para_merge():
    res = TestClient(app).get('/monitoramento-operacional')
    itens = res.json()['data']['itens']

    for item in itens:
        if item['detalhes'].get('draft') is True:
            assert item['pronto_para_merge'] is False
