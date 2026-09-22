"""Caminhos críticos da API Copilot Studio Multiagent Factory."""

import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_copilot_studio_api.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_copilot_studio_solution_generate_endpoint():
    response = client.post(
        '/v1/hub-lowcode/copilot-studio/generate',
        json={
            'solution_name': 'ReqSysLowCodeCopilot',
            'display_name': 'ReqSys Copilot Studio',
            'target_environment': 'dev',
            'dry_run': True,
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['capability'] == 'Copilot Studio Multiagent Factory P0'
    assert len(data['agents']) == 3
    assert data['orchestrator']['display_name'] == 'ReqSys Copilot Studio Orquestrador'
    assert data['package']['zip_base64']


def test_copilot_studio_solution_generate_canvas_endpoint():
    response = client.post(
        '/v1/hub-lowcode/copilot-studio/generate/canvas',
        json={
            'solution_name': 'ReqSysLowCodeCopilot',
            'display_name': 'ReqSys Copilot Studio',
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['solution_name'] == 'ReqSysLowCodeCopilot'
    assert 'Canvas da Solucao Multiagente' in data['canvas_markdown']
    assert data['orchestrator']['child_agents']


def test_copilot_studio_solution_generate_agentes_filtrados():
    response = client.post(
        '/v1/hub-lowcode/copilot-studio/generate',
        json={'agents': ['aprovacoes']},
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert len(data['agents']) == 1
    assert data['agents'][0]['key'] == 'aprovacoes'
