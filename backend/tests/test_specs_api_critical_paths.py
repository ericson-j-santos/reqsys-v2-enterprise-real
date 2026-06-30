"""Testes de caminhos críticos — API Specs SDD."""

import app.api.specs as specs_api


def _configurar_sdd_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(specs_api.settings, 'sdd_specs_path', str(tmp_path))
    specs_dir = tmp_path / 'specs'
    templates_dir = tmp_path / 'settings' / 'templates' / 'specs'
    templates_dir.mkdir(parents=True, exist_ok=True)
    return specs_dir, templates_dir


def test_specs_sdd_nao_configurado_retorna_503(client, monkeypatch):
    monkeypatch.setattr(specs_api.settings, 'sdd_specs_path', '')

    response = client.get('/v1/specs')

    assert response.status_code == 503


def test_specs_listar_features_existentes(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    feature_dir = specs_dir / 'feature-alpha'
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / 'requirements.md').write_text('# Req', encoding='utf-8')

    response = client.get('/v1/specs')

    assert response.status_code == 200
    data = response.json()['data']
    assert data[0]['slug'] == 'feature-alpha'
    assert 'requirements.md' in data[0]['arquivos']


def test_specs_exemplos_espelha_listagem(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / 'exemplo').mkdir()
    (specs_dir / 'exemplo' / 'design.md').write_text('# Design', encoding='utf-8')

    response = client.get('/v1/specs/exemplos')

    assert response.status_code == 200
    assert any(item['slug'] == 'exemplo' for item in response.json()['data'])


def test_specs_get_feature_retorna_arquivos(client, monkeypatch, tmp_path):
    specs_dir, _templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    feature_dir = specs_dir / 'feature-beta'
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / 'design.md').write_text('conteudo design', encoding='utf-8')

    response = client.get('/v1/specs/feature-beta')

    assert response.status_code == 200
    assert response.json()['data']['arquivos']['design'] == 'conteudo design'


def test_specs_criar_duplicado_retorna_409(client, monkeypatch, tmp_path):
    specs_dir, templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / 'duplicada').mkdir()
    (templates_dir / 'requirements.md').write_text('# Template', encoding='utf-8')

    response = client.post(
        '/v1/specs',
        json={
            'slug': 'duplicada',
            'titulo': 'Duplicada',
            'descricao': 'Tentativa de criar feature existente.',
            'templates': ['requirements'],
        },
    )

    assert response.status_code == 409


def test_specs_criar_a_partir_de_exemplo(client, monkeypatch, tmp_path):
    specs_dir, templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)
    exemplo = specs_dir / 'base-exemplo'
    exemplo.mkdir()
    (exemplo / 'requirements.md').write_text('Feature base-exemplo inicial', encoding='utf-8')
    (templates_dir / 'requirements.md').write_text('# Fallback', encoding='utf-8')

    response = client.post(
        '/v1/specs',
        json={
            'slug': 'nova-feature',
            'titulo': 'Nova Feature',
            'descricao': 'Copiada de exemplo.',
            'exemplo_base': 'base-exemplo',
            'templates': [],
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['slug'] == 'nova-feature'
    assert 'requirements.md' in data['arquivos_criados']
    conteudo = (specs_dir / 'nova-feature' / 'requirements.md').read_text(encoding='utf-8')
    assert 'nova-feature' in conteudo


def test_specs_template_fallback_para_md_generico(client, monkeypatch, tmp_path):
    specs_dir, templates_dir = _configurar_sdd_tmp(monkeypatch, tmp_path)
    specs_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / 'design.md').write_text('# Design generico', encoding='utf-8')

    response = client.post(
        '/v1/specs',
        json={
            'slug': 'so-design',
            'titulo': 'So Design',
            'descricao': 'Usa template .md sem variante pt-br.',
            'templates': ['design'],
        },
    )

    assert response.status_code == 200
    assert response.json()['data']['arquivos_criados'] == ['design.md']
