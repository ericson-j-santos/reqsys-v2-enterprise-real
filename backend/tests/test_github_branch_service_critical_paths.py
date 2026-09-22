"""Testes de caminhos críticos — github_branch_service."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.agile_runtime import AgileWorkItem
from app.services.github_branch_service import GithubBranchError, criar_branch_work_item


def _work_item() -> AgileWorkItem:
    return AgileWorkItem(
        id=1,
        codigo='AGI-900001',
        tipo='story',
        titulo='Branch service',
        descricao='Teste',
        prioridade='P2',
        pontos=3,
        valor_negocio=10,
        score_risco=5,
        owner_ai='backend-ia',
        status='novo',
    )


@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
def test_criar_branch_bloqueia_ambiente_prod(_gate):
    with pytest.raises(GithubBranchError, match='produtivo'):
        criar_branch_work_item(MagicMock(), _work_item(), 'prod', correlation_id='corr')


@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': False, 'detalhe': 'gate bloqueado'})
def test_criar_branch_respeita_increment_gate(_gate):
    with pytest.raises(GithubBranchError, match='gate bloqueado'):
        criar_branch_work_item(MagicMock(), _work_item(), 'dev', correlation_id='corr')


@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=False)
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
def test_criar_branch_exige_token(_gate, _token):
    with pytest.raises(GithubBranchError, match='GITHUB_TOKEN'):
        criar_branch_work_item(MagicMock(), _work_item(), 'dev', correlation_id='corr')


@patch('app.services.github_branch_service.montar_github_launchpad')
@patch('app.services.github_branch_service.github_client')
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_criar_branch_quando_ja_existe(mock_token_ok, _gate, mock_github, mock_launchpad):
    db = MagicMock()
    item = _work_item()
    mock_launchpad.return_value = {
        'repositorio': 'org/repo',
        'branch_trabalho': 'feature/agi-900001',
        'branch_base': 'main',
        'links': {},
    }
    mock_github.get_branch_sha.side_effect = lambda repo, branch: 'sha123' if branch == 'feature/agi-900001' else None

    resultado = criar_branch_work_item(db, item, 'dev', correlation_id='corr', criar_se_ausente=True)

    assert resultado['criada'] is False
    assert resultado['motivo'] == 'branch_ja_existe'


@patch('app.services.github_branch_service.registrar_evento')
@patch('app.services.github_branch_service.montar_github_launchpad')
@patch('app.services.github_branch_service.github_client')
@patch('app.services.github_branch_service.verificar_increment_gate', return_value={'permitido': True, 'detalhe': 'ok'})
@patch('app.services.github_branch_service.github_client.github_token_configurado', return_value=True)
def test_criar_branch_nova_com_sucesso(mock_token_ok, _gate, mock_github, mock_launchpad, _evento):
    db = MagicMock()
    item = _work_item()
    mock_launchpad.side_effect = [
        {
            'repositorio': 'org/repo',
            'branch_trabalho': 'feature/agi-900001',
            'branch_base': 'main',
            'links': {},
        },
        {
            'repositorio': 'org/repo',
            'branch_trabalho': 'feature/agi-900001',
            'branch_base': 'main',
            'links': {},
            'branch_existe': True,
        },
    ]
    mock_github.get_branch_sha.side_effect = lambda repo, branch: None if branch == 'feature/agi-900001' else 'sha-base'

    resultado = criar_branch_work_item(db, item, 'dev', correlation_id='corr')

    assert resultado['criada'] is True
    mock_github.create_branch.assert_called_once()
