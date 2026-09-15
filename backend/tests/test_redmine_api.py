from __future__ import annotations

import pytest

from app.services import redmine_api
from app.services.github_redmine import IntegracaoError


class _Requisito:
    codigo = 'REQ-1686'
    titulo = 'Sincronizar ReqSys com Redmine'
    sistema = 'ReqSys'
    area = 'Engenharia'
    solicitante = 'analista@reqsys.local'
    urgencia = 'alta'
    impacto_regulatorio = True
    descricao = 'Manter o lifecycle reconciliado de forma idempotente.'


def _configurar_redmine(monkeypatch):
    secrets = {
        'REDMINE_BASE_URL': 'https://redmine.example/',
        'REDMINE_API_KEY': 'segredo-de-teste',
    }
    monkeypatch.setattr(redmine_api, 'get_secret', lambda key, default='': secrets.get(key, default))


def test_montar_campos_requisito_redmine_preserva_contrato_funcional():
    campos = redmine_api.montar_campos_requisito_redmine(_Requisito())

    assert campos['subject'] == '[REQ-1686] Sincronizar ReqSys com Redmine'
    assert '*Sistema:* ReqSys' in campos['description']
    assert '*Área:* Engenharia' in campos['description']
    assert '*Solicitante:* analista@reqsys.local' in campos['description']
    assert '*Urgência:* Alta' in campos['description']
    assert '*Impacto Regulatório:* Sim' in campos['description']
    assert campos['description'].endswith(_Requisito.descricao)


def test_config_redmine_falha_fechado_sem_url(monkeypatch):
    monkeypatch.setattr(redmine_api, 'get_secret', lambda *_args, **_kwargs: '')

    with pytest.raises(IntegracaoError, match='Redmine não configurado'):
        redmine_api.obter_issue_redmine(1)


def test_obter_issue_redmine_rejeita_id_invalido_sem_chamada_externa(monkeypatch):
    monkeypatch.setattr(
        redmine_api,
        '_request_json',
        lambda *_args, **_kwargs: pytest.fail('não deveria chamar a API'),
    )

    with pytest.raises(IntegracaoError, match='maior que zero'):
        redmine_api.obter_issue_redmine(0)


def test_obter_issue_redmine_inclui_journals_e_retorna_issue(monkeypatch):
    _configurar_redmine(monkeypatch)
    captured = {}

    def fake_request(method, url, headers=None, payload=None):
        captured.update(method=method, url=url, headers=headers, payload=payload)
        return {'issue': {'id': 42, 'subject': 'REQ-1686'}}

    monkeypatch.setattr(redmine_api, '_request_json', fake_request)

    issue = redmine_api.obter_issue_redmine(42, incluir_journals=True)

    assert issue['id'] == 42
    assert captured['method'] == 'GET'
    assert captured['url'] == 'https://redmine.example/issues/42.json?include=journals'
    assert captured['headers'] == {'X-Redmine-API-Key': 'segredo-de-teste'}
    assert captured['payload'] is None


def test_obter_issue_redmine_normaliza_crlf_sem_alterar_conteudo(monkeypatch):
    _configurar_redmine(monkeypatch)
    original = 'linha 1\r\nlinha 2\rlinha 3\nlinha 4'

    monkeypatch.setattr(
        redmine_api,
        '_request_json',
        lambda *_args, **_kwargs: {
            'issue': {
                'id': 42,
                'subject': 'REQ-1686',
                'description': original,
            }
        },
    )

    issue = redmine_api.obter_issue_redmine(42)

    assert issue['description'] == 'linha 1\nlinha 2\nlinha 3\nlinha 4'
    assert '\r' not in issue['description']
    assert original == 'linha 1\r\nlinha 2\rlinha 3\nlinha 4'


def test_obter_issue_redmine_sem_journals_e_formato_invalido(monkeypatch):
    _configurar_redmine(monkeypatch)
    captured = {}

    def fake_request(method, url, headers=None, payload=None):
        captured['url'] = url
        return {'unexpected': True}

    monkeypatch.setattr(redmine_api, '_request_json', fake_request)

    with pytest.raises(IntegracaoError, match='formato esperado'):
        redmine_api.obter_issue_redmine(42, incluir_journals=False)

    assert captured['url'] == 'https://redmine.example/issues/42.json'


def test_atualizar_issue_redmine_rejeita_id_e_campos_sem_proprietario(monkeypatch):
    with pytest.raises(IntegracaoError, match='maior que zero'):
        redmine_api.atualizar_issue_redmine(0, {'subject': 'x'})

    with pytest.raises(IntegracaoError, match='campos sem propriedade ReqSys: status_id'):
        redmine_api.atualizar_issue_redmine(42, {'status_id': 3})


def test_atualizar_issue_redmine_sem_campos_efetivos_nao_chama_api(monkeypatch):
    _configurar_redmine(monkeypatch)
    monkeypatch.setattr(
        redmine_api,
        '_request_json',
        lambda *_args, **_kwargs: pytest.fail('não deveria chamar a API'),
    )

    assert redmine_api.atualizar_issue_redmine(42, {'subject': None}) == {}


def test_atualizar_issue_redmine_envia_somente_campos_reqsys(monkeypatch):
    _configurar_redmine(monkeypatch)
    captured = {}

    def fake_request(method, url, headers=None, payload=None):
        captured.update(method=method, url=url, headers=headers, payload=payload)
        return {}

    monkeypatch.setattr(redmine_api, '_request_json', fake_request)

    enviados = redmine_api.atualizar_issue_redmine(
        42,
        {'subject': '[REQ-1686] título', 'description': 'descrição'},
    )

    assert enviados == {'subject': '[REQ-1686] título', 'description': 'descrição'}
    assert captured == {
        'method': 'PUT',
        'url': 'https://redmine.example/issues/42.json',
        'headers': {'X-Redmine-API-Key': 'segredo-de-teste'},
        'payload': {'issue': enviados},
    }
