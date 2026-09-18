"""Testes de caminhos críticos — figma_github_sync."""

from unittest.mock import MagicMock, patch

from app.models.integracao_figma_github import IntegracaoFigmaGithub
from app.services import figma_github_sync as sync


def test_build_marker_e_direct_url():
    marker = sync.build_marker('file123', node_id='1:2', comment_id='c9')
    assert 'file=file123' in marker
    assert sync._direct_figma_url('file123', '1:2').endswith('node-id=1:2')


def test_extract_node_id_from_comment():
    assert sync._extract_node_id_from_comment({'client_meta': {'node_id': '12:34'}}) == '12:34'
    assert sync._extract_node_id_from_comment({'client_meta': {'node_offset': {'node_id': '9:9'}}}) == '9:9'
    assert sync._extract_node_id_from_comment({}) is None


def test_short_text_fallback():
    assert sync._short_text('', 'fallback') == 'fallback'


def test_sync_result_as_dict():
    result = sync.SyncResult(created=1, updated=2, skipped=3, conflicts=0, warnings=['w'], links=[{'id': 1}])
    data = result.as_dict()
    assert data['created'] == 1
    assert data['warnings'] == ['w']


@patch('app.services.figma_github_sync.settings')
def test_sync_enabled_respeita_flag(mock_settings):
    mock_settings.enable_figma_github_sync = True
    assert sync.sync_enabled() is True
    mock_settings.enable_figma_github_sync = False
    assert sync.sync_enabled() is False


@patch('app.services.figma_github_sync.sync_github_to_figma')
@patch('app.services.figma_github_sync.sync_figma_to_github')
def test_sync_bidirectional_agrega_resultados(mock_figma_to_github, mock_github_to_figma, db_session):
    mock_figma_to_github.return_value = sync.SyncResult(created=1, updated=0, links=[{'id': 1}])
    mock_github_to_figma.return_value = sync.SyncResult(updated=2, skipped=1)

    result = sync.sync_bidirectional(db_session, file_key='fk', repo='org/repo', include_frames=False)

    assert result.created == 1
    assert result.updated == 2
    assert result.skipped == 1


@patch('app.services.figma_github_sync.figma_client.create_comment')
def test_handle_github_issue_event_atualiza_link(mock_create_comment, db_session):
    link = IntegracaoFigmaGithub(
        figma_file_key='fk',
        figma_node_id='1:1',
        github_repo='org/repo',
        github_issue_number=10,
        github_issue_url='https://github.com/o/r/issues/10',
        status='linked',
    )
    db_session.add(link)
    db_session.commit()

    payload = {
        'action': 'closed',
        'issue': {'number': 10, 'state': 'closed', 'html_url': 'https://github.com/o/r/issues/10'},
        'repository': {'full_name': 'org/repo'},
    }

    result = sync.handle_github_issue_event(db_session, payload)

    assert result.updated == 1
    mock_create_comment.assert_called_once()


def test_handle_github_issue_event_sem_link_incrementa_skip(db_session):
    payload = {
        'action': 'opened',
        'issue': {'number': 404, 'html_url': 'https://github.com/o/r/issues/404'},
        'repository': {'full_name': 'org/repo'},
    }

    result = sync.handle_github_issue_event(db_session, payload)

    assert result.skipped == 1


@patch('app.services.figma_github_sync.figma_client.get_comments')
@patch('app.services.figma_github_sync.github_client.create_issue')
def test_sync_figma_to_github_cria_issue(mock_create_issue, mock_comments, db_session):
    mock_comments.return_value = [
        {
            'id': 'c1',
            'message': 'Comentario de design para sync',
            'client_meta': {'node_id': '1:1'},
            'user': {'handle': 'designer'},
        }
    ]
    mock_create_issue.return_value = {
        'number': 55,
        'html_url': 'https://github.com/org/repo/issues/55',
        'title': 't',
        'body': 'b',
        'state': 'open',
    }

    result = sync.sync_figma_to_github(db_session, file_key='fk', repo='org/repo', include_frames=False)

    assert result.created == 1
    mock_create_issue.assert_called_once()


@patch('app.services.figma_github_sync.figma_client.create_comment')
def test_sync_github_to_figma_atualiza_link(mock_create_comment, db_session):
    link = IntegracaoFigmaGithub(
        figma_file_key='fk',
        figma_node_id='1:1',
        github_repo='org/repo',
        github_issue_number=20,
        github_issue_url='https://github.com/org/repo/issues/20',
        status='linked',
    )
    db_session.add(link)
    db_session.commit()

    result = sync.sync_github_to_figma(db_session, file_key='fk', repo='org/repo')

    assert result.updated == 1
    mock_create_comment.assert_called_once()


def test_short_text_trunca_texto_longo():
    texto = 'x' * 120
    assert len(sync._short_text(texto, 'fb')) == 80


def test_issue_body_inclui_dev_resources():
    body = sync._issue_body(
        'fk',
        '1:1',
        'c1',
        'Resumo do frame',
        {
            'sync_kind': 'frame',
            'dev_resources': [{'name': 'Spec', 'url': 'https://example.com/spec'}],
        },
    )
    assert 'Dev resources:' in body
    assert 'Spec' in body


@patch('app.services.figma_github_sync.figma_client.get_nodes')
def test_collect_frame_sources(mock_get_nodes):
    mock_get_nodes.return_value = {
        'nodes': {
            '10:20': {
                'document': {
                    'name': 'Dashboard',
                    'type': 'FRAME',
                    'devResources': [{'name': 'API', 'url': 'https://api.example'}],
                }
            }
        }
    }
    sources = sync._collect_frame_sources('fk', ['10:20'])
    assert len(sources) == 1
    assert sources[0]['sync_kind'] == 'frame'
    assert sources[0]['name'] == 'Dashboard'


@patch('app.services.figma_github_sync.figma_client.get_comments')
def test_collect_comment_sources_ignora_resolvidos_e_sem_id(mock_comments):
    mock_comments.return_value = [
        {'id': 'c1', 'message': 'ok', 'resolved_at': '2026-01-01'},
        {'message': 'sem id'},
        {'id': 'c2', 'message': 'ativo', 'user': {'email': 'a@b.com'}},
    ]
    sources = sync._collect_comment_sources('fk')
    assert len(sources) == 1
    assert sources[0]['comment_id'] == 'c2'


@patch('app.services.figma_github_sync.github_client.create_issue', side_effect=RuntimeError('github down'))
@patch('app.services.figma_github_sync.figma_client.get_comments')
def test_sync_figma_to_github_registra_warning_quando_create_issue_falha(mock_comments, _create_issue, db_session):
    mock_comments.return_value = [{'id': 'c9', 'message': 'falha', 'client_meta': {'node_id': '1:2'}}]
    result = sync.sync_figma_to_github(db_session, file_key='fk', repo='org/repo', include_frames=False)
    assert result.created == 0
    assert any('github down' in warning for warning in result.warnings)


@patch('app.services.figma_github_sync.figma_client.get_comments', return_value=[])
def test_sync_figma_to_github_sem_dev_resources(mock_comments, db_session):
    result = sync.sync_figma_to_github(
        db_session,
        file_key='fk',
        repo='org/repo',
        include_frames=False,
        include_dev_resources=False,
    )
    assert result.created == 0
    mock_comments.assert_called_once()


def test_sync_github_to_figma_pula_sem_issue_number(db_session):
    link = IntegracaoFigmaGithub(
        figma_file_key='fk',
        github_repo='org/repo',
        status='pending',
    )
    db_session.add(link)
    db_session.commit()

    result = sync.sync_github_to_figma(db_session, file_key='fk', repo='org/repo')

    assert result.skipped == 1


@patch('app.services.figma_github_sync.figma_client.create_comment', side_effect=RuntimeError('figma down'))
def test_sync_github_to_figma_registra_warning_quando_comentario_falha(mock_comment, db_session):
    link = IntegracaoFigmaGithub(
        figma_file_key='fk',
        figma_node_id='1:1',
        github_repo='org/repo',
        github_issue_number=30,
        github_issue_url='https://github.com/org/repo/issues/30',
        status='linked',
    )
    db_session.add(link)
    db_session.commit()

    result = sync.sync_github_to_figma(db_session, repo='org/repo')

    assert result.updated == 0
    assert any('figma down' in warning for warning in result.warnings)
    mock_comment.assert_called_once()
