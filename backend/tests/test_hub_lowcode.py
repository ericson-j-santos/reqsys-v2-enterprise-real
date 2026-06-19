"""
Testes do modulo Hub Low-Code & IA.

Cobertura minima:
- status consolidado;
- pacotes IA;
- flows Power Automate;
- GitHub Actions;
- validacao de parametros.
"""

import app.api.hub_lowcode as hub_api


async def _fake_status_consolidado():
    return {
        'pacotes_configurado': False,
        'ultimo_pacote': None,
        'github_configurado': False,
        'ultimo_run': None,
        'gerado_em': '2026-06-18T00:00:00+00:00',
    }


async def _fake_listar_pacotes_ia(limit=20):
    return {
        'configurado': True,
        'itens': [
            {
                'id': 'pkg-1',
                'projeto': 'ReqSys',
                'branch': 'main',
                'commit': 'abcdef123456',
                'tech_stack': 'FastAPI/Vue',
                'total_arquivos': 10,
                'tamanho_mb': 1.2,
                'status': 'ok',
                'chave': 'sha-123',
                'gerado_em': '2026-06-18T00:00:00Z',
                'processado_em': '',
            }
        ][:limit],
        'erro': None,
    }


async def _fake_listar_flows_pa():
    return {
        'configurado': True,
        'flows': [{'id': 'flow-1', 'nome': 'ReqSys - Criar no Planner', 'estado': 'Started'}],
        'execucoes': [],
        'erro': None,
    }


async def _fake_listar_runs_github(limit=10):
    return {
        'configurado': True,
        'runs': [
            {
                'id': 1,
                'nome': 'CI',
                'workflow': 'ci.yml',
                'branch': 'main',
                'commit': 'abc12345',
                'status': 'completed',
                'conclusao': 'success',
                'criado_em': '2026-06-18T00:00:00Z',
                'url': 'https://github.com/acme/repo/actions/runs/1',
            }
        ][:limit],
        'erro': None,
    }


def test_hub_lowcode_status(client, monkeypatch):
    monkeypatch.setattr(hub_api, 'status_consolidado', _fake_status_consolidado)

    resp = client.get('/v1/hub-lowcode/status')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['pacotes_configurado'] is False
    assert body['data']['github_configurado'] is False
    assert 'gerado_em' in body['data']


def test_hub_lowcode_pacotes(client, monkeypatch):
    monkeypatch.setattr(hub_api, 'listar_pacotes_ia', _fake_listar_pacotes_ia)

    resp = client.get('/v1/hub-lowcode/pacotes?limit=1')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    data = body['data']
    assert data['configurado'] is True
    assert len(data['itens']) == 1
    assert data['itens'][0]['projeto'] == 'ReqSys'


def test_hub_lowcode_flows(client, monkeypatch):
    monkeypatch.setattr(hub_api, 'listar_flows_pa', _fake_listar_flows_pa)

    resp = client.get('/v1/hub-lowcode/flows')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    data = body['data']
    assert data['configurado'] is True
    assert data['flows'][0]['nome'] == 'ReqSys - Criar no Planner'


def test_hub_lowcode_github(client, monkeypatch):
    monkeypatch.setattr(hub_api, 'listar_runs_github', _fake_listar_runs_github)

    resp = client.get('/v1/hub-lowcode/github?limit=1')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    data = body['data']
    assert data['configurado'] is True
    assert len(data['runs']) == 1
    assert data['runs'][0]['workflow'] == 'ci.yml'


def test_hub_lowcode_limit_invalido_retorna_422(client):
    resp = client.get('/v1/hub-lowcode/github?limit=0')

    assert resp.status_code == 422
