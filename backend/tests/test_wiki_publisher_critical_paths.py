"""Testes de caminhos críticos — wiki_publisher (geração, gate GitHub e fallback)."""

import json
from unittest.mock import patch

from app.services.wiki_publisher import (
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


def test_hash_conteudo_e_deterministico():
    from app.services.wiki_publisher import _hash_conteudo

    conteudo = gerar_conteudo_wiki_requisito(_requisito())
    assert len(_hash_conteudo(conteudo)) == 64
    assert _hash_conteudo(conteudo) == _hash_conteudo(conteudo)


@patch('app.services.wiki_publisher.get_secret')
def test_checar_github_com_repo_configurado(mock_secret):
    from app.services.wiki_publisher import _checar_github

    mock_secret.side_effect = lambda key, default='': {
        'GITHUB_DOCS_REPO': 'acme/docs',
        'GITHUB_DOCS_BASE_PATH': 'docs/requisitos',
    }.get(key, default)

    with patch(
        'app.services.wiki_publisher.verificar_versao_github',
        return_value={'status': 'sincronizado', 'hash_github': 'abc', 'hash_reqsys': 'abc'},
    ) as mock_verificar:
        resultado = _checar_github('REQ-TEST-001', 'abc')

    assert resultado['status'] == 'sincronizado'
    mock_verificar.assert_called_once_with('acme/docs', 'docs/requisitos/REQ-TEST-001.md', 'abc')


@patch('app.services.wiki_publisher.get_secret')
def test_publicar_redmine_sem_config_retorna_erro(mock_secret):
    from app.services.wiki_publisher import _publicar_redmine_wiki

    mock_secret.return_value = ''
    resultado = _publicar_redmine_wiki('Requisitos/REQ-001', '# titulo', 'corr-redmine-001')

    assert resultado['publicado'] is False
    assert resultado['status_publicacao'] == 'erro'
    assert 'REDMINE' in resultado['mensagem']


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_publicar_redmine_sucesso(mock_urlopen, mock_secret):
    from app.services.wiki_publisher import _publicar_redmine_wiki

    mock_secret.side_effect = lambda key, default='': {
        'REDMINE_BASE_URL': 'https://redmine.example.com',
        'REDMINE_API_KEY': 'key-123',
        'REDMINE_PROJECT_ID': 'proj-1',
    }.get(key, default)
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{}'

    resultado = _publicar_redmine_wiki('Requisitos/REQ-001', '# titulo\n\n## Desc', 'corr-redmine-002')

    assert resultado['publicado'] is True
    assert 'wiki_url' in resultado


@patch('app.services.wiki_publisher.get_secret', return_value='')
def test_chamar_wiki_sync_sem_base_url_usa_redmine(mock_secret):
    from app.services.wiki_publisher import _chamar_wiki_sync

    with patch(
        'app.services.wiki_publisher._publicar_redmine_wiki',
        return_value={'publicado': True, 'correlation_id': 'corr-sync-001', 'status_publicacao': 'publicado'},
    ) as mock_redmine:
        resultado = _chamar_wiki_sync('Requisitos/REQ-001', '# conteudo', 'corr-sync-001')

    assert resultado['publicado'] is True
    mock_redmine.assert_called_once()


@patch('app.services.wiki_publisher.get_secret')
@patch('app.services.wiki_publisher.request.urlopen')
def test_chamar_wiki_sync_sucesso(mock_urlopen, mock_secret):
    from app.services.wiki_publisher import _chamar_wiki_sync

    mock_secret.side_effect = lambda key, default='': {
        'WIKI_SYNC_BASE_URL': 'https://wiki-sync.example.com',
        'WIKI_SYNC_TOKEN': 'token-abc',
    }.get(key, default)
    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
        {'data': {'correlationId': 'corr-sync-002'}}
    ).encode()

    resultado = _chamar_wiki_sync('Requisitos/REQ-001', '# conteudo', 'corr-sync-001')

    assert resultado['publicado'] is True
    assert resultado['correlation_id'] == 'corr-sync-002'


@patch('app.services.wiki_publisher.get_secret', return_value='acme/docs')
def test_consultar_status_wiki_com_github_repo(mock_secret):
    with patch(
        'app.services.wiki_publisher._checar_github',
        return_value={'status': 'divergente', 'hash_github': 'aaa', 'hash_reqsys': 'bbb'},
    ):
        resultado = consultar_status_wiki(_requisito())

    assert resultado['wiki_page_title'] == 'Requisitos/REQ-TEST-001'
    assert resultado['github_version']['status'] == 'divergente'
