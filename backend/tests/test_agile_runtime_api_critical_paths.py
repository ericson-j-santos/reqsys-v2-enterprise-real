"""Testes de caminhos críticos — API Agile Runtime."""

import os
from unittest.mock import patch

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_agile_runtime_critical.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')


def _criar_work_item(client):
    response = client.post(
        '/v1/agile-runtime/work-items',
        json={
            'tipo': 'story',
            'titulo': 'Story critical paths',
            'descricao': 'Validacao de rotas complementares do agile runtime.',
            'prioridade': 'P2',
            'pontos': 3,
            'valor_negocio': 50,
            'score_risco': 10,
            'owner_ai': 'backend-ia',
        },
    )
    assert response.status_code == 200
    return response.json()['data']['id']


def test_work_item_inexistente_retorna_404(client):
    response = client.get('/v1/agile-runtime/work-items/999999/ai-routing/preview')

    assert response.status_code == 404


def test_sprint_data_fim_invalida_retorna_422(client):
    response = client.post(
        '/v1/agile-runtime/sprints',
        json={
            'nome': 'Sprint invalida',
            'objetivo': 'Datas invertidas',
            'data_inicio': '2026-07-01',
            'data_fim': '2026-06-01',
            'capacidade_pontos': 10,
            'pontos_comprometidos': 5,
        },
    )

    assert response.status_code == 422


def test_listar_sprints_e_work_items(client):
    _criar_work_item(client)

    sprints = client.get('/v1/agile-runtime/sprints')
    itens = client.get('/v1/agile-runtime/work-items')

    assert sprints.status_code == 200
    assert itens.status_code == 200
    assert isinstance(sprints.json()['data'], list)
    assert len(itens.json()['data']) >= 1


def test_ai_routing_preview_e_apply(client):
    work_item_id = _criar_work_item(client)

    preview = client.get(f'/v1/agile-runtime/work-items/{work_item_id}/ai-routing/preview')
    assert preview.status_code == 200
    assert preview.json()['data']['modo'] == 'preview'

    apply = client.post(
        f'/v1/agile-runtime/work-items/{work_item_id}/ai-routing/apply',
        headers={'X-Correlation-Id': 'corr-agile-routing'},
    )
    assert apply.status_code == 200
    assert apply.json()['data']['modo'] == 'aplicado'


def test_criar_branch_github_trata_erro_de_servico(client):
    work_item_id = _criar_work_item(client)

    with patch(
        'app.api.agile_runtime.criar_branch_work_item',
        side_effect=ValueError('ambiente invalido'),
    ):
        response = client.post(
            f'/v1/agile-runtime/work-items/{work_item_id}/github/branch',
            json={'ambiente': 'dev', 'criar_se_ausente': True, 'aplicar_branch_no_item': True},
        )

    assert response.status_code == 422
