"""Gaps de cobertura — API ia, specs, auth (fase 8)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.specs as specs_api
from app.main import app
from app.services.gemini import GeminiIndisponivel

client = TestClient(app)


def _configurar_sdd(monkeypatch, tmp_path, *, com_templates=True):
    monkeypatch.setattr(specs_api.settings, 'sdd_specs_path', str(tmp_path))
    specs_dir = tmp_path / 'specs'
    specs_dir.mkdir(parents=True, exist_ok=True)
    if com_templates:
        templates_dir = tmp_path / 'settings' / 'templates' / 'specs'
        templates_dir.mkdir(parents=True, exist_ok=True)
    return specs_dir


# --- ia.py ---


def test_ia_status_sem_chaves_expoe_avisos_e_passos_pendentes():
    with patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = ''
        mock_settings.gemini_model = 'gemini-2.0-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'
        resp = client.get('/v1/ia/status')

    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['configurada'] is False
    assert data['fallback_ativo'] is False
    assert len(data['avisos']) == 2
    assert len(data['passos_pendentes']) == 2


def test_ia_sugerir_descricao_retorna_503_quando_indisponivel():
    with patch('app.api.ia.sugerir_descricao', side_effect=GeminiIndisponivel('offline')), \
         patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = 'fake'
        mock_settings.gemini_model = 'gemini-2.0-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'
        resp = client.post('/v1/ia/sugerir-descricao', json={'titulo': 'Titulo teste'})

    assert resp.status_code == 503


def test_ia_classificar_urgencia_retorna_503_quando_indisponivel():
    with patch('app.api.ia.classificar_urgencia', side_effect=GeminiIndisponivel('offline')), \
         patch('app.api.ia.settings') as mock_settings:
        mock_settings.gemini_api_key = 'fake'
        mock_settings.gemini_model = 'gemini-2.0-flash'
        mock_settings.groq_api_key = ''
        mock_settings.groq_model = 'llama-3.3-70b-versatile'
        resp = client.post(
            '/v1/ia/classificar-urgencia',
            json={'titulo': 'Bug', 'descricao': 'Falha critica'},
        )

    assert resp.status_code == 503


# --- specs.py ---


def test_specs_listar_ignora_arquivo_solto_no_diretorio(client, monkeypatch, tmp_path):
    specs_dir = _configurar_sdd(monkeypatch, tmp_path)
    (specs_dir / 'not-a-dir.md').write_text('# solto', encoding='utf-8')
    feature_dir = specs_dir / 'feature-valida'
    feature_dir.mkdir()
    (feature_dir / 'requirements.md').write_text('# ok', encoding='utf-8')

    resp = client.get('/v1/specs')

    assert resp.status_code == 200
    slugs = [item['slug'] for item in resp.json()['data']]
    assert slugs == ['feature-valida']


def test_specs_templates_vazio_quando_diretorio_ausente(client, monkeypatch, tmp_path):
    _configurar_sdd(monkeypatch, tmp_path, com_templates=False)

    resp = client.get('/v1/specs/templates')

    assert resp.status_code == 200
    assert resp.json()['data'] == []


def test_specs_get_arquivo_inexistente_retorna_404(client, monkeypatch, tmp_path):
    specs_dir = _configurar_sdd(monkeypatch, tmp_path)
    feature_dir = specs_dir / 'feature-x'
    feature_dir.mkdir()
    (feature_dir / 'requirements.md').write_text('# ok', encoding='utf-8')

    resp = client.get('/v1/specs/feature-x/inexistente.md')

    assert resp.status_code == 404


def test_specs_criar_ignora_template_inexistente(client, monkeypatch, tmp_path):
    _configurar_sdd(monkeypatch, tmp_path, com_templates=True)

    resp = client.post(
        '/v1/specs',
        json={
            'slug': 'nova-feature',
            'titulo': 'Nova',
            'descricao': 'Sem templates validos',
            'templates': ['template-inexistente'],
        },
    )

    assert resp.status_code == 200
    assert resp.json()['data']['arquivos_criados'] == []


def test_specs_atualizar_arquivo_inexistente_retorna_404(client, monkeypatch, tmp_path):
    specs_dir = _configurar_sdd(monkeypatch, tmp_path)
    (specs_dir / 'feature-y').mkdir()

    resp = client.put(
        '/v1/specs/feature-y/design.md',
        json={'conteudo': '# novo'},
    )

    assert resp.status_code == 404


# --- auth.py ---


def test_login_azure_token_invalido_retorna_401():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = 'tenant-teste'
    settings.azure_client_id = 'client-teste'
    try:
        with patch('app.api.auth.validar_token_azure', side_effect=ValueError('token expirado')):
            resp = client.post('/v1/auth/azure', json={'id_token': 'token.invalido'})
        assert resp.status_code == 401
        assert 'inválido' in resp.json()['detail']
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client


def test_azure_code_id_token_invalido_apos_exchange_retorna_401():
    from app.core.config import settings

    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    settings.azure_tenant_id = 'tenant-teste'
    settings.azure_client_id = 'client-teste'
    try:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {'id_token': 'mock.id.token'}

        with patch('app.api.auth.httpx.post', return_value=mock_response), \
             patch('app.api.auth.validar_token_azure', side_effect=ValueError('assinatura invalida')):
            resp = client.post(
                '/v1/auth/azure-code',
                json={'code': 'c', 'verifier': 'v', 'redirectUri': 'https://app.example/callback'},
            )
        assert resp.status_code == 401
        assert 'ID token inválido' in resp.json()['detail']
    finally:
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client
