"""Testes de caminhos críticos — wiki_publisher (geração, gate GitHub e fallback)."""

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
