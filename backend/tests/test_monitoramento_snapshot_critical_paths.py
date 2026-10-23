"""Testes de caminhos críticos — snapshot operacional de monitoramento."""

import asyncio
import gzip
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.schemas.monitoramento_operacional import ItemMonitorado
from app.services import monitoramento_snapshot as snapshot


@pytest.fixture(autouse=True)
def _govbi_base_url_aprovada(monkeypatch):
    monkeypatch.setattr(snapshot.settings, 'govbi_base_url', 'https://govbi.example')
    monkeypatch.setattr(snapshot.settings, 'govbi_allowed_hosts', 'govbi.example')


class _StreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        await self.response.aclose()
        return False


class _AsyncClient:
    def __init__(self, response):
        self.response = response
        self.stream = MagicMock(return_value=_StreamContext(response))
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False


def _stream_client(response):
    return _AsyncClient(response)


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


@pytest.mark.parametrize('status_code', [401, 404, 503])
@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_vermelho_quando_http_nao_comprova_saude(mock_client_cls, status_code):
    mock_client = _stream_client(httpx.Response(status_code))
    mock_client_cls.return_value = mock_client

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['http_status'] == status_code
    assert detalhes['saude_externa'] == 'indisponivel'
    assert detalhes['motivo'] == 'status_http_inesperado'
    mock_client.stream.assert_called_once_with('GET', 'https://govbi.example/actuator/health', headers={'Accept-Encoding': 'identity'})
    assert mock_client_cls.call_args.kwargs['follow_redirects'] is False
    assert mock_client_cls.call_args.kwargs['trust_env'] is False


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


@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_verde_quando_actuator_confirma_up(mock_client_cls):
    mock_client = _stream_client(httpx.Response(200, stream=httpx.ByteStream(b'{"status":"UP"}')))
    mock_client_cls.return_value = mock_client

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'verde'
    assert detalhes['http_status'] == 200
    assert detalhes['configuracao'] == 'valida'
    assert detalhes['saude_externa'] == 'saudavel'
    mock_client.stream.assert_called_once_with('GET', 'https://govbi.example/actuator/health', headers={'Accept-Encoding': 'identity'})


@pytest.mark.parametrize(
    ('body', 'motivo'),
    [
        (b'not-json', 'resposta_json_invalida'),
        (b'{"status":"DOWN"}', 'contrato_health_invalido'),
        (b'["UP"]', 'contrato_health_invalido'),
    ],
)
@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_rejeita_resposta_200_fora_do_contrato(mock_client_cls, body, motivo):
    response = httpx.Response(200, stream=httpx.ByteStream(body))
    mock_client = _stream_client(response)
    mock_client_cls.return_value = mock_client

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['saude_externa'] == 'indisponivel'
    assert detalhes['motivo'] == motivo




@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_rejeita_corpo_oversized_e_fecha_stream(mock_client_cls):
    response = httpx.Response(200, stream=httpx.ByteStream(b'x' * (snapshot.GOVBI_HEALTH_MAX_BYTES + 1)))
    mock_client_cls.return_value = _stream_client(response)

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['motivo'] == 'resposta_excede_limite'
    assert response.is_closed is True


@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_rejeita_content_length_oversized_sem_ler_corpo(mock_client_cls):
    response = httpx.Response(
        200,
        headers={'content-length': str(snapshot.GOVBI_HEALTH_MAX_BYTES + 1)},
        content=b'{}',
    )
    response.aiter_raw = MagicMock(side_effect=AssertionError('corpo não deve ser lido'))
    mock_client_cls.return_value = _stream_client(response)

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['motivo'] == 'resposta_excede_limite'
    response.aiter_raw.assert_not_called()
    assert response.is_closed is True


@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_rejeita_content_encoding_comprimido_antes_da_leitura(mock_client_cls):
    response = httpx.Response(
        200,
        headers={'content-encoding': 'gzip'},
        content=gzip.compress(b'{"status":"UP"}'),
    )
    response.aiter_raw = MagicMock(side_effect=AssertionError('corpo comprimido não deve ser lido'))
    mock_client_cls.return_value = _stream_client(response)

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['motivo'] == 'content_encoding_nao_permitido'
    response.aiter_raw.assert_not_called()
    assert response.is_closed is True


@patch('app.services.monitoramento_snapshot.httpx.AsyncClient')
def test_estado_govbi_cancela_stream_gotejante_no_limite_total(mock_client_cls, monkeypatch):
    class RespostaGotejante:
        status_code = 200
        headers = {}
        fechada = False

        async def aiter_raw(self):
            while True:
                await asyncio.sleep(0.01)
                yield b'{'

        async def aclose(self):
            self.fechada = True

    response = RespostaGotejante()
    client = _stream_client(response)
    mock_client_cls.return_value = client
    monkeypatch.setattr(snapshot, 'GOVBI_HEALTH_TOTAL_TIMEOUT_SECONDS', 0.05)

    estado, detalhes = snapshot._estado_govbi()

    assert estado == 'vermelho'
    assert detalhes['motivo'] == 'tempo_total_excedido'
    assert response.fechada is True
    assert client.closed is True


@pytest.mark.parametrize('timeout_invalido', [float('nan'), float('inf'), float('-inf'), 0.0, -1.0])
def test_estado_govbi_bloqueia_timeout_nao_finito_ou_nao_positivo(monkeypatch, timeout_invalido):
    monkeypatch.setattr(snapshot.settings, 'govbi_timeout_seconds', timeout_invalido)
    with patch('app.services.monitoramento_snapshot.httpx.AsyncClient') as client:
        estado, detalhes = snapshot._estado_govbi()

    assert estado == 'bloqueado'
    assert detalhes['configuracao'] == 'invalida'
    assert detalhes['saude_externa'] == 'nao_avaliada'
    client.assert_not_called()


@patch('app.services.monitoramento_snapshot.httpx.AsyncClient', side_effect=RuntimeError('timeout'))
def test_estado_govbi_vermelho_quando_probe_falha(_mock_client):
    estado, detalhes = snapshot._estado_govbi()
    assert estado == 'vermelho'
    assert 'erro' in detalhes


@pytest.mark.parametrize('base_url', ['', 'https://govbi.fly.dev', 'https://govbi.fly.io'])
def test_estado_govbi_bloqueado_sem_url_aprovada(monkeypatch, base_url):
    monkeypatch.setattr(snapshot.settings, 'govbi_base_url', base_url)
    with patch('app.services.monitoramento_snapshot.httpx.AsyncClient') as client:
        estado, detalhes = snapshot._estado_govbi()

    assert estado == 'bloqueado'
    assert detalhes['fonte'] == 'configuracao'
    assert detalhes['modo'] == 'bloqueado'
    assert detalhes['configuracao'] == 'invalida'
    assert detalhes['saude_externa'] == 'nao_avaliada'
    assert 'base_url' not in detalhes
    client.assert_not_called()


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


@pytest.mark.parametrize('estado_geral', ['amarelo', 'verde'])
def test_estado_conectores_preserva_sinal_operacional(estado_geral):
    resumo = {'estado_geral': estado_geral, 'total': 2}
    with patch.object(snapshot, 'resumo_conectores', return_value=resumo):
        estado, detalhes = snapshot._estado_conectores()

    assert estado == estado_geral
    assert detalhes == resumo


@pytest.mark.parametrize('estado', ['vermelho', 'amarelo', 'desconhecido', 'verde'])
def test_classificacao_preserva_estado_sem_bloqueio(estado):
    item = ItemMonitorado(
        tipo='integracao', referencia='controle', titulo='Controle',
        estado=estado, severidade='media', origem='teste',
    )
    esperado = 'amarelo' if estado == 'desconhecido' else estado
    assert snapshot.classificar_estado_geral([item]) == esperado


@patch.dict('os.environ', {'GITHUB_TOKEN': 'unused-test-token', 'REQSYS_GITHUB_REPO': 'org/repo'})
def test_estado_ci_verde_exige_sem_falhas_e_sem_execucoes():
    resumo = {
        'score_saude': 100, 'decisao': 'ok', 'total_runs': 1,
        'falhas': [], 'em_execucao': [],
    }
    with patch.object(snapshot, 'GitHubActionsClient') as client:
        client.return_value.listar_runs.return_value = []
        with patch.object(snapshot, 'classificar_runs', return_value=resumo):
            estado, detalhes = snapshot._estado_ci()

    assert estado == 'verde'
    assert detalhes['modo'] == 'live'
    assert detalhes['falhas'] == 0

