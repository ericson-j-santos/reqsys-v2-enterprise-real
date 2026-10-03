"""Testes de caminhos críticos — wiki_publisher (geração, gate GitHub e fallback)."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services import wiki_publisher as module
from app.services.wiki_publisher import (
    _chamar_wiki_sync,
    _hash_conteudo,
    _publicar_redmine_wiki,
    consultar_status_wiki,
    gerar_conteudo_wiki_requisito,
    publicar_requisito_no_wiki,
)


@pytest.fixture(autouse=True)
def _circuit_breaker_isolado():
    module.reset_circuit_breakers()
    yield
    module.reset_circuit_breakers()


def _requisito(**overrides):
    base = {
        'codigo': 'REQ-TEST-001',
        'titulo': 'Requisito de teste',
        'descricao': 'Descrição operacional',
        'status': 'recebido',
        'area': 'TI',
        'sistema': 'ReqSys',
        'solicitante': 'qa@example.com',
        'urgencia': 'alta',
        'impacto_regulatorio': True,
        'criado_em': '2026-06-28T12:00:00Z',
    }
    base.update(overrides)
    return base


def test_gerar_conteudo_wiki_requisito_inclui_campos_criticos():
    conteudo = gerar_conteudo_wiki_requisito(_requisito())

    assert 'REQ-TEST-001' in conteudo
    assert 'Requisito de teste' in conteudo
    assert 'Impacto Regulatório' in conteudo
    assert 'Sim' in conteudo
    assert 'Descrição operacional' in conteudo


@patch('app.services.wiki_publisher.get_secret', return_value='')
def test_consultar_status_wiki_sem_github_repo(_secret):
    resultado = consultar_status_wiki(_requisito())

    assert resultado['wiki_page_title'] == 'Requisitos/REQ-TEST-001'
    assert resultado['github_version']['status'] == 'verificacao_desabilitada'


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.verificar_versao_github')
def test_checar_github_quando_repo_configurado(mock_verificar, mock_secret):
    from app.services.wiki_publisher import _checar_github

    mock_secret.side_effect = lambda key, default='': {
        'GITHUB_DOCS_REPO': 'acme/docs',
        'GITHUB_DOCS_BASE_PATH': 'docs/requisitos',
    }.get(key, default)
    mock_verificar.return_value = {'status': 'sincronizado'}

    resultado = _checar_github('REQ-TEST-001', 'hash123')

    assert resultado == {'status': 'sincronizado'}
    mock_verificar.assert_called_once()


@patch('app.services.wiki_publisher.get_secret', return_value='')
@patch('app.services.wiki_publisher._chamar_wiki_sync')
@patch('app.services.wiki_publisher._checar_github', return_value=None)
def test_publicar_requisito_sem_github_config_chama_wiki_sync(mock_checar, mock_sync, _secret):
    mock_sync.return_value = {
        'publicado': True,
        'correlation_id': 'corr-wiki-001',
        'wiki_page_title': 'Requisitos/REQ-TEST-001',
        'status_publicacao': 'publicado',
        'mensagem': 'ok',
    }

    resultado = publicar_requisito_no_wiki(_requisito(), correlation_id='corr-wiki-001')

    assert resultado['publicado'] is True
    mock_sync.assert_called_once()


@patch('app.services.wiki_publisher.get_secret', return_value='acme/docs')
@patch('app.services.wiki_publisher._chamar_wiki_sync')
def test_publicar_requisito_ignora_quando_github_sincronizado(mock_sync, _secret):
    with patch(
        'app.services.wiki_publisher._checar_github',
        return_value={'status': 'sincronizado', 'hash_github': 'abc', 'hash_reqsys': 'abc'},
    ):
        resultado = publicar_requisito_no_wiki(_requisito(), correlation_id='corr-wiki-002')

    assert resultado['publicado'] is False
    assert resultado['status_publicacao'] == 'ignorado_conteudo_identico'
    mock_sync.assert_not_called()


@patch('app.services.wiki_publisher.get_secret', return_value='acme/docs')
@patch('app.services.wiki_publisher._chamar_wiki_sync')
def test_publicar_requisito_bloqueia_divergencia_github(mock_sync, _secret):
    with patch(
        'app.services.wiki_publisher._checar_github',
        return_value={'status': 'divergente', 'hash_github': 'aaa', 'hash_reqsys': 'bbb'},
    ):
        resultado = publicar_requisito_no_wiki(_requisito(), correlation_id='corr-wiki-003')

    assert resultado['publicado'] is False
    assert resultado['status_publicacao'] == 'bloqueado_divergencia_github'
    mock_sync.assert_not_called()


@patch('app.services.wiki_publisher.get_secret', return_value='')
@patch('app.services.wiki_publisher._publicar_redmine_wiki')
@patch('app.services.wiki_publisher._checar_github', return_value=None)
def test_publicar_requisito_forca_atualizacao_apos_divergencia(mock_checar, mock_redmine, _secret):
    mock_redmine.return_value = {
        'publicado': True,
        'correlation_id': 'corr-wiki-004',
        'wiki_page_title': 'Requisitos/REQ-TEST-001',
        'status_publicacao': 'publicado',
        'mensagem': 'publicado',
    }

    with patch(
        'app.services.wiki_publisher._checar_github',
        return_value={'status': 'divergente', 'hash_github': 'aaa', 'hash_reqsys': 'bbb'},
    ):
        resultado = publicar_requisito_no_wiki(
            _requisito(),
            correlation_id='corr-wiki-004',
            forcar_atualizacao=True,
        )

    assert resultado['publicado'] is True
    mock_redmine.assert_called_once()


def test_hash_conteudo_e_geracao_sem_impacto_regulatorio():
    conteudo = gerar_conteudo_wiki_requisito(_requisito(impacto_regulatorio=False))
    assert 'Não' in conteudo
    assert len(_hash_conteudo(conteudo)) == 64


@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_sem_config(mock_secret):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': '',
        'REDMINE_API_KEY': '',
        'REDMINE_PROJECT_ID': '',
    }.get(key, default)

    resultado = _publicar_redmine_wiki('Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-001')

    assert resultado['publicado'] is False
    assert resultado['status_publicacao'] == 'erro'
    assert 'nao configurados' in resultado['mensagem']


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_sucesso(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'api-key',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.return_value.__enter__.return_value = MagicMock()

    resultado = _publicar_redmine_wiki('Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-002')

    assert resultado['publicado'] is True
    assert resultado['status_publicacao'] == 'publicado'
    assert 'wiki' in resultado['wiki_url']


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_http_error(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'api-key',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.side_effect = HTTPError('https://redmine.example.com', 422, 'fail', {}, BytesIO(b'detail'))

    resultado = _publicar_redmine_wiki('Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-003')

    assert resultado['publicado'] is False
    assert 'Erro HTTP 422' in resultado['mensagem']


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_url_error(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'api-key',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.side_effect = URLError('offline')

    resultado = _publicar_redmine_wiki('Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-004', sleep=lambda _s: None)

    assert resultado['publicado'] is False
    assert 'Falha de conexao' in resultado['mensagem']


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_tenta_novamente_apos_falha_transitoria(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'api-key',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    chamadas = {'n': 0}
    sonos = []

    def fake_urlopen(req, timeout):
        chamadas['n'] += 1
        if chamadas['n'] < 3:
            raise URLError('timeout de rede')
        return MagicMock()

    mock_urlopen.side_effect = fake_urlopen

    resultado = _publicar_redmine_wiki('Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-005', sleep=sonos.append)

    assert resultado['publicado'] is True
    assert chamadas['n'] == 3
    assert len(sonos) == 2


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_wiki_circuito_abre_apos_falhas_consecutivas(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'api-key',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.side_effect = URLError('redmine fora do ar')

    for _ in range(3):
        resultado = _publicar_redmine_wiki(
            'Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-006', sleep=lambda _s: None, max_retries=1,
        )
        assert resultado['publicado'] is False

    resultado_circuito_aberto = _publicar_redmine_wiki(
        'Requisitos/REQ-TEST-001', '# titulo', 'corr-redmine-007', sleep=lambda _s: None,
    )

    assert resultado_circuito_aberto['publicado'] is False
    assert "Circuito 'wiki_publisher_redmine.example.com' aberto" in resultado_circuito_aberto['mensagem']


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_chamar_wiki_sync_service_sucesso(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'WIKI_SYNC_BASE_URL': 'https://wiki-sync.example.com',
        'WIKI_SYNC_TOKEN': 'token-sync',
    }.get(key, default)
    body = json.dumps({'data': {'correlationId': 'corr-sync-001'}}).encode('utf-8')
    mock_urlopen.return_value.__enter__.return_value.read.return_value = body

    resultado = _chamar_wiki_sync('Requisitos/REQ-TEST-001', '# titulo', 'corr-sync-001')

    assert resultado['publicado'] is True
    assert resultado['correlation_id'] == 'corr-sync-001'


@patch('app.services.wiki_publisher.request.urlopen')
@patch('app.services.wiki_publisher.get_secret')
def test_chamar_wiki_sync_service_http_error(mock_secret, mock_urlopen):
    mock_secret.side_effect = lambda key, default='': {
        'WIKI_SYNC_BASE_URL': 'https://wiki-sync.example.com',
        'WIKI_SYNC_TOKEN': '',
    }.get(key, default)
    mock_urlopen.side_effect = HTTPError('https://wiki-sync.example.com', 500, 'fail', {}, BytesIO(b'detail'))

    resultado = _chamar_wiki_sync('Requisitos/REQ-TEST-001', '# titulo', 'corr-sync-002')

    assert resultado['publicado'] is False
    assert 'Erro HTTP 500' in resultado['mensagem']


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.verificar_versao_github')
def test_checar_github_quando_repo_configurado(mock_verificar, mock_secret):
    from app.services.wiki_publisher import _checar_github

    mock_secret.side_effect = lambda key, default='': {
        'GITHUB_DOCS_REPO': 'acme/docs',
        'GITHUB_DOCS_BASE_PATH': 'docs/requisitos',
    }.get(key, default)
    mock_verificar.return_value = {'status': 'sincronizado'}

    resultado = _checar_github('REQ-TEST-001', 'hash123')

    assert resultado == {'status': 'sincronizado'}
    mock_verificar.assert_called_once()


@patch('app.services.wiki_publisher._checar_github')
@patch('app.services.wiki_publisher.get_secret')
def test_consultar_status_wiki_com_repo_configurado(mock_secret, mock_checar):
    mock_secret.return_value = 'acme/docs'
    mock_checar.return_value = {'status': 'sincronizado', 'hash_github': 'abc', 'hash_reqsys': 'abc'}

    resultado = consultar_status_wiki(_requisito())

    assert resultado['wiki_page_title'] == 'Requisitos/REQ-TEST-001'
    assert resultado['github_version']['status'] == 'sincronizado'
