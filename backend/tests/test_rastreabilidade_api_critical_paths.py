"""Testes de caminhos críticos — API rastreabilidade (matriz e filtros)."""

import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_rastreabilidade_critical.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')


def test_vinculos_recentes_filtra_por_provedor(client):
    criado = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Rastreabilidade filtro',
            'descricao': 'Criar requisito para vinculo gitlab.',
            'urgencia': 'media',
            'area': 'QA',
            'sistema': 'Git',
            'solicitante': 'qa@reqsys.local',
            'impacto_regulatorio': False,
        },
    )
    requisito_id = criado.json()['data']['id']
    codigo = criado.json()['data'].get('codigo') or f'REQ-{requisito_id}'

    manual = client.post(
        f'/v1/rastreabilidade/requisitos/{requisito_id}/vinculos',
        json={
            'tipo': 'commit',
            'provedor': 'gitlab',
            'repo': 'grupo/projeto',
            'referencia': 'abc123',
            'url': 'https://gitlab.com/grupo/projeto/-/commit/abc123',
        },
    )
    assert manual.status_code == 200

    filtrado = client.get('/v1/rastreabilidade/recentes?provedor=gitlab&limit=10')
    assert filtrado.status_code == 200
    vinculos = filtrado.json()['data']['vinculos']
    assert any(v['provedor'] == 'gitlab' for v in vinculos)


def test_matriz_rastreabilidade_inclui_work_item(client):
    criado = client.post(
        '/v1/requisitos',
        json={
            'titulo': 'Matriz rastreabilidade',
            'descricao': 'Requisito com work item vinculado na matriz.',
            'urgencia': 'alta',
            'area': 'Agile',
            'sistema': 'Runtime',
            'solicitante': 'qa@reqsys.local',
            'impacto_regulatorio': False,
        },
    )
    requisito_id = criado.json()['data']['id']

    work_item = client.post(
        '/v1/agile-runtime/work-items',
        json={
            'tipo': 'story',
            'titulo': 'Historia matriz',
            'descricao': 'Work item ligado ao requisito para matriz.',
            'prioridade': 'P1',
            'pontos': 5,
            'valor_negocio': 80,
            'score_risco': 10,
            'owner_ai': 'qa-ia',
            'requisito_id': requisito_id,
        },
    )
    assert work_item.status_code == 200
    agi_codigo = work_item.json()['data']['codigo']

    vinculo = client.post(
        f'/v1/rastreabilidade/requisitos/{requisito_id}/vinculos',
        json={
            'tipo': 'pr',
            'provedor': 'github',
            'repo': 'org/repo',
            'referencia': '99',
            'url': 'https://github.com/org/repo/pull/99',
        },
    )
    assert vinculo.status_code == 200

    matriz = client.get('/v1/rastreabilidade/matriz?limit=20')
    assert matriz.status_code == 200
    linhas = matriz.json()['data']['linhas']
    assert any(linha['historia'] == agi_codigo for linha in linhas)
    assert any(linha['entrega'].startswith('PR #') for linha in linhas)
