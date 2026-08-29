from __future__ import annotations

import json

import pytest

from app.api.teams_github_actions import TeamsGithubActionsCardRequest, construir_cartao
from app.services import teams_github_actions as service


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b'' if payload is None else json.dumps(payload).encode('utf-8')

    def json(self):
        return self._payload


class _FakeAsyncClient:
    calls: list[dict] = []
    response = _FakeResponse(204)

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, *, json: dict, headers: dict):
        type(self).calls.append({'url': url, 'json': json, 'headers': headers})
        return type(self).response


def _config(monkeypatch, *, enabled: bool = True) -> None:
    values = {
        'TEAMS_GITHUB_ACTIONS_ENABLED': 'true' if enabled else 'false',
        'TEAMS_GITHUB_ACTIONS_REPO': 'ericson-j-santos/reqsys-v2-enterprise-real',
        'TEAMS_GITHUB_ACTIONS_WORKFLOW': 'actions-dispatcher.yml',
        'TEAMS_GITHUB_ACTIONS_DISPATCH_REF': 'main',
    }
    monkeypatch.setattr(service, 'get_secret', lambda name, default='': values.get(name, default))
    monkeypatch.setattr(service.settings, 'github_pat', 'token-de-teste')


def test_cartao_bot_expoe_somente_acoes_governadas():
    card = construir_cartao(
        TeamsGithubActionsCardRequest(
            titulo='Falha no CI',
            descricao='Escolha a verificacao.',
            ref='feature/teste',
            interaction_mode='bot',
            github_url='https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions',
        ),
        'corr-123',
    )

    action_set = card['body'][-1]
    actions = action_set['actions']
    assert card['version'] == '1.4'
    assert actions[0]['type'] == 'Action.Execute'
    assert actions[0]['verb'] == 'reqsys.github.actions.dispatch'
    assert actions[0]['data'] == {
        'reqsys_action': 'github_actions_dispatch',
        'mode': 'essential',
        'ref': 'feature/teste',
        'correlation_id': 'corr-123',
    }
    assert actions[0]['fallback']['type'] == 'Action.Submit'
    assert actions[1]['data']['mode'] == 'all'
    assert actions[2]['type'] == 'Action.OpenUrl'


def test_cartao_flow_usa_action_submit():
    card = construir_cartao(
        TeamsGithubActionsCardRequest(ref='main', interaction_mode='flow'),
        'corr-flow',
    )
    actions = card['body'][-1]['actions']
    assert [action['type'] for action in actions] == ['Action.Submit', 'Action.Submit']
    assert {action['data']['mode'] for action in actions} == {'essential', 'all'}


@pytest.mark.asyncio
async def test_dispatch_usa_workflow_central_sem_aceitar_repo_do_cliente(monkeypatch):
    _config(monkeypatch)
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            'workflow_run_id': 123,
            'html_url': 'https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/123',
        },
    )
    monkeypatch.setattr(service.httpx, 'AsyncClient', _FakeAsyncClient)

    result = await service.despachar_verificacoes_github(
        mode='essential',
        target_ref='feature/teste',
        correlation_id='corr-123',
        actor='usuario-aad',
    )

    assert result['dispatched'] is True
    assert result['run_id'] == 123
    call = _FakeAsyncClient.calls[0]
    assert call['url'].endswith(
        '/repos/ericson-j-santos/reqsys-v2-enterprise-real/actions/workflows/actions-dispatcher.yml/dispatches'
    )
    assert call['json'] == {
        'ref': 'main',
        'inputs': {'ref': 'feature/teste', 'mode': 'essential'},
    }
    assert call['headers']['Authorization'] == 'Bearer token-de-teste'
    assert 'token-de-teste' not in json.dumps(result)


@pytest.mark.asyncio
async def test_dispatch_rejeita_ref_invalida_antes_de_chamar_github(monkeypatch):
    _config(monkeypatch)
    _FakeAsyncClient.calls = []
    monkeypatch.setattr(service.httpx, 'AsyncClient', _FakeAsyncClient)

    with pytest.raises(service.TeamsGithubActionsError, match='Ref Git invalida'):
        await service.despachar_verificacoes_github(
            mode='essential',
            target_ref='../main',
            correlation_id='corr-123',
            actor='usuario-aad',
        )

    assert _FakeAsyncClient.calls == []


@pytest.mark.asyncio
async def test_dispatch_bloqueia_quando_feature_flag_desabilitada(monkeypatch):
    _config(monkeypatch, enabled=False)

    with pytest.raises(service.TeamsGithubActionsError, match='desabilitadas') as exc:
        await service.despachar_verificacoes_github(
            mode='all',
            target_ref='main',
            correlation_id='corr-123',
            actor='usuario-aad',
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_dispatch_nao_vaza_resposta_do_github_em_erro(monkeypatch):
    _config(monkeypatch)
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.response = _FakeResponse(403, {'message': 'token interno e detalhes sensiveis'})
    monkeypatch.setattr(service.httpx, 'AsyncClient', _FakeAsyncClient)

    with pytest.raises(service.TeamsGithubActionsError, match='sem permissao') as exc:
        await service.despachar_verificacoes_github(
            mode='all',
            target_ref='main',
            correlation_id='corr-403',
            actor='usuario-aad',
        )

    assert exc.value.status_code == 502
    assert 'token interno' not in str(exc.value)
