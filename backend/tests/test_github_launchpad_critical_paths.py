"""Testes de caminhos críticos — github_launchpad (ambientes e links)."""

from unittest.mock import patch

import pytest

from app.models.agile_runtime import AgileWorkItem
from app.services.github_launchpad import (
    branch_base_por_ambiente,
    montar_github_launchpad,
    normalizar_ambiente_launchpad,
)


def _item(**kwargs) -> AgileWorkItem:
    base = {
        'id': 10,
        'codigo': 'AGI-LP-10',
        'tipo': 'story',
        'titulo': 'Launchpad paths',
        'descricao': 'Cobertura de caminhos do launchpad GitHub.',
        'repositorio': 'org/repo',
        'pontos': 0,
        'valor_negocio': 0,
        'score_risco': 0,
        'ambiente_deploy': 'none',
        'ci_status': 'unknown',
        'deploy_status': 'not_started',
    }
    base.update(kwargs)
    return AgileWorkItem(**base)


def test_normalizar_ambiente_invalido():
    with pytest.raises(ValueError, match='invalido'):
        normalizar_ambiente_launchpad('ambiente-inexistente')


def test_branch_base_por_ambiente_homolog():
    assert branch_base_por_ambiente('hml') == 'hml'


@patch('app.services.github_launchpad.github_client.github_token_configurado', return_value=True)
@patch('app.services.github_launchpad.github_client.get_branch_sha', return_value='abc123')
def test_montar_launchpad_homolog_com_branch_deploy(_sha, _token):
    item = _item(
        ambiente_deploy='homolog',
        branch='feature/hml/agi-10',
        change_url='https://github.com/org/repo/pull/1',
        ci_url='https://github.com/org/repo/actions/runs/1',
        deploy_url='https://app.example/deploy/1',
    )
    payload = montar_github_launchpad(item, 'homolog')

    assert payload['branch_trabalho'] == 'feature/hml/agi-10'
    assert payload['links']['change_request'] == item.change_url
    assert payload['links']['ci'] == item.ci_url
    assert payload['links']['deploy'] == item.deploy_url
    assert 'criar_branch_api' in payload['acoes_disponiveis']
    assert payload['branch_existe'] is True


@patch('app.services.github_launchpad.github_client.github_token_configurado', return_value=False)
def test_montar_launchpad_sem_repo_configurado(_token):
    item = _item(repositorio='')
    with patch('app.services.github_launchpad.settings') as mock_settings:
        mock_settings.github_alm_repo = ''
        with pytest.raises(ValueError, match='Repositorio'):
            montar_github_launchpad(item, 'dev')
