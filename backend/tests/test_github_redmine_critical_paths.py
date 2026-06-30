"""Caminhos críticos — integração GitHub/Redmine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.services.github_redmine import (
    IntegracaoError,
    _parse_repo,
    _request_json,
    fetch_github_issues,
    github_redmine_import_enabled,
    publish_requisito_to_redmine,
)


def test_parse_repo_rejeita_formato_invalido():
    with pytest.raises(IntegracaoError, match='Repo inválido'):
        _parse_repo('owner-only')


def test_github_redmine_import_enabled_respeita_flag(monkeypatch):
    monkeypatch.setenv('ENABLE_GITHUB_REDMINE_IMPORT', 'false')
    assert github_redmine_import_enabled() is False
    monkeypatch.setenv('ENABLE_GITHUB_REDMINE_IMPORT', 'yes')
    assert github_redmine_import_enabled() is True


def test_request_json_propaga_http_error():
    error = HTTPError('https://api.github.com', 403, 'forbidden', hdrs=None, fp=MagicMock(read=lambda: b'rate limit'))
    with patch('app.services.github_redmine.request.urlopen', side_effect=error):
        with pytest.raises(IntegracaoError, match='HTTP 403'):
            _request_json('GET', 'https://api.github.com/repos/o/r/issues')


def test_request_json_propaga_url_error():
    with patch('app.services.github_redmine.request.urlopen', side_effect=URLError('offline')):
        with pytest.raises(IntegracaoError, match='Falha de rede'):
            _request_json('GET', 'https://api.github.com/repos/o/r/issues')


def test_fetch_github_issues_ignora_pull_requests(monkeypatch):
    payload = [
        {'number': 1, 'title': 'issue', 'state': 'open', 'labels': [], 'pull_request': {'url': 'x'}},
        {'number': 2, 'title': 'real issue', 'state': 'open', 'labels': [{'name': 'bug'}], 'html_url': 'https://x'},
    ]
    with patch('app.services.github_redmine._request_json', return_value=payload):
        with patch('app.services.github_redmine.get_secret', return_value=''):
            issues = fetch_github_issues('owner/repo', labels=['bug'])
    assert len(issues) == 1
    assert issues[0]['number'] == 2


def test_publish_requisito_to_redmine_sem_config_retorna_warning():
    class _Req:
        titulo = 'Teste'
        descricao = 'Descricao longa de teste'
        urgencia = 'media'

    with patch('app.services.github_redmine.get_secret', return_value=''):
        resultado = publish_requisito_to_redmine(_Req())
    assert resultado['issue_principal_id'] is None
    assert resultado['warnings']


def test_request_json_post_com_payload():
    response = MagicMock()
    response.read.return_value = json.dumps({'ok': True}).encode()
    response.__enter__ = lambda self: self
    response.__exit__ = MagicMock(return_value=False)
    with patch('app.services.github_redmine.request.urlopen', return_value=response):
        data = _request_json('POST', 'https://example.com', payload={'a': 1})
    assert data == {'ok': True}
