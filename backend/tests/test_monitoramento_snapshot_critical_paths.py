"""Testes de caminhos críticos — snapshot operacional de monitoramento."""

from unittest.mock import MagicMock, patch

from app.schemas.monitoramento_operacional import ItemMonitorado
from app.services import monitoramento_snapshot as snapshot


def test_classificar_estado_geral_lista_vazia():
    assert snapshot.classificar_estado_geral([]) == 'desconhecido'


def test_classificar_estado_geral_bloqueante_sem_estado_bloqueado():
    itens = [
        ItemMonitorado(tipo='a', referencia='1', titulo='bloq', estado='verde', severidade='alta', origem='x', bloqueante=True),
    ]
    assert snapshot.classificar_estado_geral(itens) == 'bloqueado'


def test_classificar_estado_geral_prioriza_bloqueio():
    itens = [
        ItemMonitorado(tipo='a', referencia='1', titulo='ok', estado='verde', severidade='baixa', origem='x'),
        ItemMonitorado(tipo='b', referencia='2', titulo='bloq', estado='bloqueado', severidade='alta', origem='x'),
    ]
    assert snapshot.classificar_estado_geral(itens) == 'bloqueado'


def test_estado_de_score_mapeia_faixas():
    assert snapshot._estado_de_score(96) == 'verde'
    assert snapshot._estado_de_score(85) == 'amarelo'
    assert snapshot._estado_de_score(50) == 'vermelho'


def test_resolver_modo_coleta():
    assert snapshot._resolver_modo_coleta({'a': {'modo': 'live'}, 'b': {'modo': 'live'}}) == 'live'
    assert snapshot._resolver_modo_coleta({'a': {'modo': 'live'}, 'b': {'modo': 'preview'}}) == 'hibrido'
    assert snapshot._resolver_modo_coleta({'a': {'modo': 'preview'}}) == 'preview'


@patch('app.services.monitoramento_snapshot.httpx.Client')
def test_estado_govbi_amarelo_quando_5xx(mock_client_cls):
    mock_response = MagicMock(status_code=503)
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'amarelo'
    assert detalhes['http_status'] == 503


@patch('app.services.monitoramento_snapshot.resumo_conectores')
def test_estado_conectores_mapeia_bloqueado(mock_resumo):
    mock_resumo.return_value = {'estado_geral': 'bloqueado'}
    estado, _ = snapshot._estado_conectores()
    assert estado == 'vermelho'


@patch('app.services.monitoramento_snapshot.resumo_conectores')
def test_estado_conectores_desconhecido(mock_resumo):
    mock_resumo.return_value = {'estado_geral': 'outro'}
    estado, _ = snapshot._estado_conectores()
    assert estado == 'desconhecido'


@patch.dict('os.environ', {'GITHUB_TOKEN': 'tok', 'REQSYS_GITHUB_REPO': 'org/repo'})
@patch('app.services.monitoramento_snapshot.GitHubActionsClient')
def test_estado_ci_amarelo_quando_em_execucao(mock_client_cls):
    mock_client_cls.return_value.listar_runs.return_value = []
    with patch('app.services.monitoramento_snapshot.classificar_runs', return_value={
        'score_saude': 98,
        'decisao': 'ok',
        'total_runs': 1,
        'falhas': [],
        'em_execucao': [{'id': 1}],
    }):
        estado, detalhes = snapshot._estado_ci()
    assert estado == 'amarelo'
    assert detalhes['modo'] == 'live'


@patch.dict('os.environ', {'GITHUB_TOKEN': 'tok', 'REQSYS_GITHUB_REPO': 'org/repo'})
@patch('app.services.monitoramento_snapshot.GitHubActionsClient', side_effect=RuntimeError('api down'))
def test_estado_ci_preview_quando_api_falha(_mock_client):
    estado, detalhes = snapshot._estado_ci()
    assert estado == 'amarelo'
    assert detalhes['modo'] == 'preview'
    assert 'erro' in detalhes


@patch('app.services.monitoramento_snapshot.httpx.Client')
def test_estado_govbi_verde_quando_health_ok(mock_client_cls):
    mock_response = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'verde'
    assert detalhes['http_status'] == 200


@patch('app.services.monitoramento_snapshot.httpx.Client', side_effect=RuntimeError('timeout'))
def test_estado_govbi_vermelho_quando_probe_falha(_mock_client):
    estado, detalhes = snapshot._estado_govbi()
    assert estado == 'vermelho'
    assert 'erro' in detalhes


@patch.dict('os.environ', {}, clear=True)
def test_estado_ci_preview_sem_token():
    estado, detalhes = snapshot._estado_ci()
    assert estado == 'amarelo'
    assert detalhes['modo'] == 'preview'


@patch.dict('os.environ', {'GITHUB_TOKEN': 'tok', 'REQSYS_GITHUB_REPO': 'org/repo'})
@patch('app.services.monitoramento_snapshot.GitHubActionsClient')
def test_estado_ci_vermelho_quando_ha_falhas(mock_client_cls):
    mock_client_cls.return_value.listar_runs.return_value = []
    with patch('app.services.monitoramento_snapshot.classificar_runs', return_value={
        'score_saude': 40,
        'decisao': 'bloquear',
        'total_runs': 2,
        'falhas': [{'id': 1}],
        'em_execucao': [],
    }):
        estado, detalhes = snapshot._estado_ci()

    assert estado == 'vermelho'
    assert detalhes['modo'] == 'live'


@patch('app.services.monitoramento_snapshot._estado_govbi', return_value=('verde', {'http_status': 200}))
@patch('app.services.monitoramento_snapshot._estado_ci', return_value=('amarelo', {'modo': 'preview'}))
@patch('app.services.monitoramento_snapshot._estado_conectores', return_value=('verde', {'estado_geral': 'verde'}))
def test_criar_snapshot_operacional_compoe_itens(_c, _ci, _g):
    payload = snapshot.criar_snapshot_operacional('corr-mon-001')

    assert payload.correlation_id == 'corr-mon-001'
    assert payload.modo_coleta in {'preview', 'hibrido', 'live'}
    assert payload.resumo.total_itens >= 5
    assert any(item.referencia == 'REQSYS-OPER-004' for item in payload.itens)
