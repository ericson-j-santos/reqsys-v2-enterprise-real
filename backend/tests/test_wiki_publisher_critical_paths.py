"""Testes de caminhos críticos — wiki_publisher (geração, gate GitHub e fallback)."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.services.wiki_publisher import (
    _chamar_wiki_sync,
    _publicar_redmine_wiki,
    consultar_status_wiki,
    gerar_conteudo_wiki_requisito,
    publicar_requisito_no_wiki,
)


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


@patch('app.services.wiki_publisher.get_secret', return_value='')
def test_publicar_redmine_wiki_sem_credenciais(_secret):
    resultado = _publicar_redmine_wiki('Requisitos/REQ-001', '# titulo', 'corr-redmine-001')

    assert resultado['publicado'] is False
    assert resultado['status_publicacao'] == 'erro'
    assert 'nao configurados' in resultado['mensagem']


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_publicar_redmine_wiki_sucesso(mock_urlopen, mock_secret):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'key-1',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

    resultado = _publicar_redmine_wiki('Requisitos/REQ-001', '# titulo', 'corr-redmine-002')

    assert resultado['publicado'] is True
    assert resultado['status_publicacao'] == 'publicado'
    assert 'redmine.example.com' in resultado['wiki_url']


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_publicar_redmine_wiki_erro_http(mock_urlopen, mock_secret):
    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'key-1',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.side_effect = HTTPError(
        url='https://redmine.example.com',
        code=422,
        msg='Unprocessable',
        hdrs={},
        fp=BytesIO(b'invalid payload'),
    )

    resultado = _publicar_redmine_wiki('Requisitos/REQ-001', '# titulo', 'corr-redmine-003')

    assert resultado['publicado'] is False
    assert 'HTTP 422' in resultado['mensagem']


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_chamar_wiki_sync_sucesso(mock_urlopen, mock_secret):
    mock_secret.side_effect = lambda key, default='': {
        'WIKI_SYNC_BASE_URL': 'https://wiki-sync.example.com',
        'WIKI_SYNC_TOKEN': 'token-1',
    }.get(key, default)
    body = json.dumps({'data': {'correlationId': 'corr-sync-001'}}).encode('utf-8')
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
    mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

    resultado = _chamar_wiki_sync('Requisitos/REQ-001', '# titulo', 'corr-sync-001')

    assert resultado['publicado'] is True
    assert resultado['correlation_id'] == 'corr-sync-001'


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_chamar_wiki_sync_erro_conexao(mock_urlopen, mock_secret):
    mock_secret.side_effect = lambda key, default='': {
        'WIKI_SYNC_BASE_URL': 'https://wiki-sync.example.com',
        'WIKI_SYNC_TOKEN': '',
    }.get(key, default)
    mock_urlopen.side_effect = URLError('connection refused')

    resultado = _chamar_wiki_sync('Requisitos/REQ-001', '# titulo', 'corr-sync-002')

    assert resultado['publicado'] is False
    assert 'Falha de conexao' in resultado['mensagem']


@patch('app.services.wiki_publisher.get_secret', return_value='acme/docs')
@patch('app.services.wiki_publisher._checar_github')
def test_consultar_status_wiki_com_github(mock_checar, _secret):
    mock_checar.return_value = {
        'status': 'sincronizado',
        'arquivo_github': 'docs/requisitos/REQ-TEST-001.md',
        'hash_github': 'abc',
        'hash_reqsys': 'abc',
    }

    resultado = consultar_status_wiki(_requisito())

    assert resultado['github_version']['status'] == 'sincronizado'
