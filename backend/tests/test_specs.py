"""
Testes do modulo Specs SDD.

Cobertura minima:
- listagem vazia;
- templates;
- criacao de spec a partir de template;
- leitura e atualizacao de arquivo;
- validacoes de erro.
"""

import app.api.specs as specs_api


def _configurar_sdd_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(specs_api.settings, 'sdd_specs_path', str(tmp_path))
    specs_dir = tmp_path / 'specs'
    templates_dir = tmp_path / 'settings' / 'templates' / 'specs'
    templates_dir.mkdir(parents=True, exist_ok=True)
    return specs_dir, templates_dir


def test_specs_listagem_vazia_quando_diretorio_nao_existe(client, monkeypatch, tmp_path):
    _configurar_sdd_tmp(monkeypatch, tmp_path)

    resp = client.get('/v1/specs')

    assert resp.status_code == 200
    assert resp.json()['success'] is True
    assert resp.json()['data'] == []


def test_specs_templates_retorna_nomes(client, monkeypatch, tmp_path):
    _specs_dir, templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    (templates_dir / 'requirements.pt-br.md').write_text('# Requirements', encoding='utf-8')
    (templates_dir / 'design.md').write_text('# Design', encoding='utf-8')

    resp = client.get('/v1/specs/templates')

    assert resp.status_code == 200
    assert resp.json()['data'] == ['design', 'requirements']


def test_specs_criar_feature_com_template(client, monkeypatch, tmp_path):
    specs_dir, templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / 'requirements.pt-br.md').write_text('# Requisitos\n\nConteudo base.', encoding='utf-8')

    resp = client.post('/v1/specs', json={
        'slug': 'Minha Feature SDD',
        'titulo': 'Minha Feature SDD',
        'descricao': 'Feature criada em teste automatizado.',
        'autor': 'pytest',
        'templates': ['requirements'],
    })

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['slug'] == 'minha-feature-sdd'
    assert data['arquivos_criados'] == ['requirements.md']
    assert (specs_dir / 'minha-feature-sdd' / 'requirements.md').exists()


def test_specs_ler_e_atualizar_arquivo(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    feature_dir = specs_dir / 'feature-teste'
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / 'requirements.md').write_text('conteudo inicial', encoding='utf-8')

    leitura = client.get('/v1/specs/feature-teste/requirements')
    assert leitura.status_code == 200
    assert leitura.json()['data']['conteudo'] == 'conteudo inicial'

    atualizacao = client.put(
        '/v1/specs/feature-teste/requirements',
        json={'conteudo': 'conteudo atualizado'},
    )
    assert atualizacao.status_code == 200

    nova_leitura = client.get('/v1/specs/feature-teste/requirements.md')
    assert nova_leitura.json()['data']['conteudo'] == 'conteudo atualizado'


def test_specs_feature_inexistente_retorna_404(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)

    resp = client.get('/v1/specs/nao-existe')

    assert resp.status_code == 404


def test_specs_slug_invalido_retorna_400(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)

    resp = client.post('/v1/specs', json={
        'slug': 'a',
        'titulo': 'Slug invalido',
        'descricao': 'Teste de validacao.',
        'templates': [],
    })

    assert resp.status_code == 400
