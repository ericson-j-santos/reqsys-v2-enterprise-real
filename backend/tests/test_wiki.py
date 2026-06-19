"""
Testes do modulo Wiki.

Cobertura minima:
- status de requisito existente;
- publicacao individual com mock;
- publicacao em lote com mock;
- requisito inexistente;
- propagacao de correlation_id.
"""

import app.api.wiki as wiki_api


def _criar_requisito(client, titulo='Requisito para teste Wiki') -> int:
    payload = {
        'titulo': titulo,
        'descricao': 'Descricao detalhada do requisito para teste automatizado de wiki.',
        'urgencia': 'alta',
        'area': 'TI',
        'sistema': 'ReqSys',
        'solicitante': 'pytest',
        'impacto_regulatorio': False,
    }
    resp = client.post('/v1/requisitos', json=payload)
    assert resp.status_code == 200
    return resp.json()['data']['id']


def _wiki_status_fake(_requisito_dict):
    return {
        'wiki_page_title': 'REQ-TESTE - Requisito Wiki',
        'github_version': {
            'status': 'verificacao_desabilitada',
            'arquivo_github': None,
            'hash_github': None,
            'hash_reqsys': 'hash-local',
            'mensagem': 'Verificacao GitHub desabilitada no teste.',
        },
    }


def _publicacao_fake(_requisito_dict, correlation_id, forcar_atualizacao):
    return {
        'publicado': True,
        'correlation_id': correlation_id,
        'wiki_page_title': 'REQ-TESTE - Requisito Wiki',
        'status_publicacao': 'publicado',
        'github_version': None,
        'mensagem': 'Publicado com sucesso no mock.',
        'forcar_atualizacao': forcar_atualizacao,
    }


def test_wiki_status_requisito_existente(client, monkeypatch):
    requisito_id = _criar_requisito(client, 'Requisito Wiki Status')
    monkeypatch.setattr(wiki_api, 'consultar_status_wiki', _wiki_status_fake)

    resp = client.get(f'/v1/wiki/requisitos/{requisito_id}/status')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['requisito_id'] == requisito_id
    assert body['data']['wiki_page_title'] == 'REQ-TESTE - Requisito Wiki'


def test_wiki_publicar_requisito_com_mock(client, monkeypatch):
    requisito_id = _criar_requisito(client, 'Requisito Wiki Publicar')
    monkeypatch.setattr(wiki_api, 'publicar_requisito_no_wiki', _publicacao_fake)

    resp = client.post(
        f'/v1/wiki/requisitos/{requisito_id}/publicar',
        json={'forcar_atualizacao': True, 'correlation_id': 'corr-wiki-body'},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == 'corr-wiki-body'
    assert body['data']['correlation_id'] == 'corr-wiki-body'
    assert body['data']['publicado'] is True
    assert body['data']['status_publicacao'] == 'publicado'
    assert body['data']['forcar_atualizacao'] is True


def test_wiki_publicar_usa_correlation_header(client, monkeypatch):
    requisito_id = _criar_requisito(client, 'Requisito Wiki Correlation')
    monkeypatch.setattr(wiki_api, 'publicar_requisito_no_wiki', _publicacao_fake)

    resp = client.post(
        f'/v1/wiki/requisitos/{requisito_id}/publicar',
        json={'forcar_atualizacao': False},
        headers={'X-Correlation-ID': 'corr-wiki-header'},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['meta']['correlation_id'] == 'corr-wiki-header'
    assert body['data']['correlation_id'] == 'corr-wiki-header'


def test_wiki_requisito_inexistente_retorna_404(client):
    resp = client.get('/v1/wiki/requisitos/999999999/status')

    assert resp.status_code == 404


def test_wiki_publicar_lote_com_mock(client, monkeypatch):
    _criar_requisito(client, 'Requisito Wiki Lote')
    monkeypatch.setattr(wiki_api, 'publicar_requisito_no_wiki', _publicacao_fake)

    resp = client.post(
        '/v1/wiki/requisitos/publicar-lote',
        json={'forcar_atualizacao': False},
        headers={'X-Correlation-ID': 'corr-wiki-lote'},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == 'corr-wiki-lote'
    assert body['data']['total'] >= 1
    assert body['data']['publicados'] >= 1
    assert isinstance(body['data']['itens'], list)
