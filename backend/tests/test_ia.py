"""
Testes do módulo IA Assistente (Gemini + Groq fallback).
Cobertura: endpoints /status, /resumir, /sugerir-descricao, /classificar-urgencia,
           tracker de cota, fallback Gemini → Groq.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini import _UsageTracker, get_uso, get_uso_groq

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def auth_headers():
    resp = client.post('/v1/auth/login', json={'email': 'ericsonjosedossantos@tieri659.onmicrosoft.com'})
    token = resp.json()['data']['access_token']
    return {'Authorization': f'Bearer {token}'}


# ---------------------------------------------------------------------------
# GET /v1/ia/status
# ---------------------------------------------------------------------------

class TestIAStatus:
    def test_status_retorna_200(self, auth_headers):
        resp = client.get('/v1/ia/status', headers=auth_headers)
        assert resp.status_code == 200

    def test_status_tem_campo_configurada(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'configurada' in data
        assert isinstance(data['configurada'], bool)

    def test_status_tem_campo_modelo(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'modelo' in data
        assert data['modelo'] == 'gemini-3.5-flash'

    def test_status_tem_cota(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'cota' in data
        cota = data['cota']
        for campo in ('req_ultimo_minuto', 'req_hoje', 'limite_por_minuto',
                      'limite_por_dia', 'restante_minuto', 'restante_dia', 'pct_dia_usado'):
            assert campo in cota, f'Campo ausente na cota: {campo}'

    def test_cota_limites_free_tier(self, auth_headers):
        cota = client.get('/v1/ia/status', headers=auth_headers).json()['data']['cota']
        assert cota['limite_por_minuto'] == 15
        assert cota['limite_por_dia'] == 1500

    def test_cota_restante_nunca_negativa(self, auth_headers):
        cota = client.get('/v1/ia/status', headers=auth_headers).json()['data']['cota']
        assert cota['restante_minuto'] >= 0
        assert cota['restante_dia'] >= 0

    def test_cota_pct_entre_0_e_100(self, auth_headers):
        cota = client.get('/v1/ia/status', headers=auth_headers).json()['data']['cota']
        assert 0.0 <= cota['pct_dia_usado'] <= 100.0

    def test_status_tem_provedores(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'provedores' in data
        assert 'gemini' in data['provedores']
        assert 'groq' in data['provedores']

    def test_status_tem_fallback_ativo(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'fallback_ativo' in data
        assert isinstance(data['fallback_ativo'], bool)

    def test_groq_cota_limites_free_tier(self, auth_headers):
        cota = client.get('/v1/ia/status', headers=auth_headers).json()['data']['provedores']['groq']['cota']
        assert cota['limite_por_minuto'] == 30
        assert cota['limite_por_dia'] == 14400


# ---------------------------------------------------------------------------
# Tracker de cota (testa a lógica isolada sem chamar nenhuma IA)
# ---------------------------------------------------------------------------

class TestUsageTracker:
    def test_tracker_inicia_zerado(self):
        tracker = _UsageTracker(limite_por_minuto=15, limite_por_dia=1500)
        snap = tracker.snapshot()
        assert snap['req_hoje'] == 0
        assert snap['req_ultimo_minuto'] == 0
        assert snap['restante_dia'] == 1500
        assert snap['restante_minuto'] == 15

    def test_registrar_incrementa_contadores(self):
        tracker = _UsageTracker(limite_por_minuto=15, limite_por_dia=1500)
        tracker.registrar()
        tracker.registrar()
        snap = tracker.snapshot()
        assert snap['req_hoje'] == 2
        assert snap['req_ultimo_minuto'] == 2
        assert snap['restante_dia'] == 1498
        assert snap['restante_minuto'] == 13

    def test_pct_calculado_corretamente(self):
        tracker = _UsageTracker(limite_por_minuto=15, limite_por_dia=1500)
        for _ in range(150):
            tracker.registrar()
        snap = tracker.snapshot()
        assert snap['pct_dia_usado'] == 10.0

    def test_tracker_groq_limites_proprios(self):
        tracker = _UsageTracker(limite_por_minuto=30, limite_por_dia=14400)
        snap = tracker.snapshot()
        assert snap['limite_por_minuto'] == 30
        assert snap['limite_por_dia'] == 14400
        assert snap['restante_minuto'] == 30
        assert snap['restante_dia'] == 14400

    def test_get_uso_e_acessivel(self):
        snap = get_uso()
        assert isinstance(snap, dict)
        assert 'req_hoje' in snap

    def test_get_uso_groq_e_acessivel(self):
        snap = get_uso_groq()
        assert isinstance(snap, dict)
        assert 'limite_por_dia' in snap
        assert snap['limite_por_dia'] == 14400


# ---------------------------------------------------------------------------
# POST /v1/ia/resumir — com mock do Gemini
# ---------------------------------------------------------------------------

class TestIAResumir:
    def test_resumir_sem_chave_retorna_503(self, auth_headers):
        with patch('app.api.ia.settings') as mock_settings:
            mock_settings.gemini_api_key = ''
            mock_settings.gemini_model = 'gemini-2.0-flash'
            mock_settings.groq_api_key = ''
            mock_settings.groq_model = 'llama-3.3-70b-versatile'
            resp = client.post('/v1/ia/resumir',
                               json={'titulo': 'Teste', 'descricao': 'Descricao de teste'},
                               headers=auth_headers)
        assert resp.status_code == 503

    def test_resumir_com_mock_retorna_resumo(self, auth_headers):
        with patch('app.services.gemini._gerar', return_value='Resumo gerado pelo mock.'):
            resp = client.post('/v1/ia/resumir',
                               json={'titulo': 'Titulo teste', 'descricao': 'Descricao longa de teste'},
                               headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['resumo'] == 'Resumo gerado pelo mock.'
        assert data['provedor'] == 'gemini'

    def test_resumir_payload_invalido_retorna_422(self, auth_headers):
        resp = client.post('/v1/ia/resumir', json={'descricao': 'sem titulo'}, headers=auth_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/ia/sugerir-descricao — com mock do Gemini
# ---------------------------------------------------------------------------

class TestIASugerirDescricao:
    def test_sugerir_com_mock_retorna_descricao(self, auth_headers):
        with patch('app.services.gemini._gerar', return_value='Descricao sugerida pelo mock.'):
            resp = client.post('/v1/ia/sugerir-descricao',
                               json={'titulo': 'Titulo', 'area': 'Credito', 'sistema': 'Portal'},
                               headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert 'descricao_sugerida' in data
        assert data['provedor'] == 'gemini'

    def test_sugerir_area_sistema_opcionais(self, auth_headers):
        with patch('app.services.gemini._gerar', return_value='Descricao.'):
            resp = client.post('/v1/ia/sugerir-descricao',
                               json={'titulo': 'Apenas titulo'},
                               headers=auth_headers)
        assert resp.status_code == 200

    def test_sugerir_payload_invalido_retorna_422(self, auth_headers):
        resp = client.post('/v1/ia/sugerir-descricao', json={}, headers=auth_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/ia/classificar-urgencia — com mock do Gemini
# ---------------------------------------------------------------------------

class TestIAClassificarUrgencia:
    def test_classificar_com_mock_alta(self, auth_headers):
        resposta_gemini = 'URGENCIA: alta\nJUSTIFICATIVA: Impacto critico em producao.'
        with patch('app.services.gemini._gerar', return_value=resposta_gemini):
            resp = client.post('/v1/ia/classificar-urgencia',
                               json={'titulo': 'Bug critico', 'descricao': 'Sistema parado.'},
                               headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['urgencia'] == 'alta'
        assert 'justificativa' in data
        assert data['provedor'] == 'gemini'

    def test_classificar_com_mock_baixa(self, auth_headers):
        resposta_gemini = 'URGENCIA: baixa\nJUSTIFICATIVA: Melhoria estetica sem impacto operacional.'
        with patch('app.services.gemini._gerar', return_value=resposta_gemini):
            resp = client.post('/v1/ia/classificar-urgencia',
                               json={'titulo': 'Ajuste de cor', 'descricao': 'Mudar cor do botao.'},
                               headers=auth_headers)
        data = resp.json()['data']
        assert data['urgencia'] == 'baixa'

    def test_classificar_payload_invalido_retorna_422(self, auth_headers):
        resp = client.post('/v1/ia/classificar-urgencia',
                           json={'titulo': 'sem descricao'},
                           headers=auth_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Fallback Gemini → Groq (mock de ambos os providers)
# ---------------------------------------------------------------------------

class TestFallbackGroq:
    def test_fallback_ativado_quando_gemini_falha(self, auth_headers):
        """Quando Gemini lança GeminiIndisponivel e Groq está configurado, usa Groq."""
        from app.services.gemini import GeminiIndisponivel

        def gemini_falha(*args, **kwargs):
            raise GeminiIndisponivel('Quota esgotada')

        with patch('app.services.gemini._gerar', side_effect=gemini_falha), \
             patch('app.services.gemini._gerar_groq', return_value='Resposta via Groq.') as mock_groq, \
             patch('app.api.ia.settings') as mock_cfg:
            mock_cfg.gemini_api_key = 'fake-gemini'
            mock_cfg.gemini_model = 'gemini-2.0-flash'
            mock_cfg.groq_api_key = 'fake-groq'
            mock_cfg.groq_model = 'llama-3.3-70b-versatile'
            resp = client.post('/v1/ia/resumir',
                               json={'titulo': 'Teste fallback', 'descricao': 'Desc.'},
                               headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['resumo'] == 'Resposta via Groq.'
        assert data['provedor'] == 'groq'
        mock_groq.assert_called_once()

    def test_sem_fallback_retorna_503_quando_ambos_falham(self, auth_headers):
        """Se Gemini falha e Groq não está configurado, retorna 503."""
        from app.services.gemini import GeminiIndisponivel

        with patch('app.api.ia.settings') as mock_cfg:
            mock_cfg.gemini_api_key = ''
            mock_cfg.gemini_model = 'gemini-2.0-flash'
            mock_cfg.groq_api_key = ''
            mock_cfg.groq_model = 'llama-3.3-70b-versatile'
            resp = client.post('/v1/ia/resumir',
                               json={'titulo': 'Teste', 'descricao': 'Desc.'},
                               headers=auth_headers)

        assert resp.status_code == 503

    def test_groq_mock_sugerir_descricao(self, auth_headers):
        """Groq como fallback também funciona para sugerir-descricao."""
        from app.services.gemini import GeminiIndisponivel

        with patch('app.services.gemini._gerar', side_effect=GeminiIndisponivel('quota')), \
             patch('app.services.gemini._gerar_groq', return_value='Descricao via Groq.'), \
             patch('app.api.ia.settings') as mock_cfg:
            mock_cfg.gemini_api_key = 'fake-gemini'
            mock_cfg.gemini_model = 'gemini-2.0-flash'
            mock_cfg.groq_api_key = 'fake-groq'
            mock_cfg.groq_model = 'llama-3.3-70b-versatile'
            resp = client.post('/v1/ia/sugerir-descricao',
                               json={'titulo': 'Titulo', 'area': 'TI', 'sistema': 'API'},
                               headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()['data']['provedor'] == 'groq'


# ---------------------------------------------------------------------------
# Teste real Gemini/Groq (skip se chave não configurada ou sem quota)
# ---------------------------------------------------------------------------

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')


def _gemini_funcional() -> bool:
    if not GEMINI_KEY:
        return False
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=GEMINI_KEY)
        m = genai.GenerativeModel('gemini-2.0-flash')
        m.generate_content('ok')
        return True
    except Exception:
        return False


def _groq_funcional() -> bool:
    if not GROQ_KEY:
        return False
    try:
        from groq import Groq  # type: ignore
        c = Groq(api_key=GROQ_KEY)
        c.chat.completions.create(model='llama-3.3-70b-versatile', messages=[{'role': 'user', 'content': 'ok'}])
        return True
    except Exception:
        return False


_GEMINI_OK = _gemini_funcional()
_GROQ_OK = _groq_funcional()


@pytest.mark.skipif(not _GEMINI_OK, reason='GEMINI_API_KEY não configurada ou sem quota')
class TestGeminiReal:
    def test_sugerir_descricao_retorna_texto(self, auth_headers):
        resp = client.post('/v1/ia/sugerir-descricao',
                           json={'titulo': 'Validacao de CPF no cadastro', 'area': 'Credito', 'sistema': 'Portal Rural'},
                           headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert len(data['descricao_sugerida']) > 20
        assert data['provedor'] == 'gemini'

    def test_classificar_urgencia_retorna_valor_valido(self, auth_headers):
        resp = client.post('/v1/ia/classificar-urgencia',
                           json={'titulo': 'Erro critico em producao', 'descricao': 'Sistema de pagamentos parado afetando todos os clientes.'},
                           headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['urgencia'] in ('baixa', 'media', 'alta', 'critica')
        assert len(data['justificativa']) > 5

    def test_cota_incrementa_apos_chamadas(self, auth_headers):
        antes = client.get('/v1/ia/status', headers=auth_headers).json()['data']['cota']['req_hoje']
        client.post('/v1/ia/sugerir-descricao',
                    json={'titulo': 'Teste cota', 'area': 'TI', 'sistema': 'API'},
                    headers=auth_headers)
        depois = client.get('/v1/ia/status', headers=auth_headers).json()['data']['cota']['req_hoje']
        assert depois > antes


@pytest.mark.skipif(not _GROQ_OK, reason='GROQ_API_KEY não configurada ou sem quota')
class TestGroqReal:
    def test_groq_sugerir_descricao(self, auth_headers):
        """Chama Groq diretamente via fallback (Gemini configurado mas sem quota real)."""
        from app.services.gemini import GeminiIndisponivel

        with patch('app.services.gemini._gerar', side_effect=GeminiIndisponivel('sem quota')):
            resp = client.post('/v1/ia/sugerir-descricao',
                               json={'titulo': 'Autenticacao via SSO', 'area': 'Seguranca', 'sistema': 'Portal'},
                               headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()['data']
        assert len(data['descricao_sugerida']) > 20
        assert data['provedor'] == 'groq'

    def test_groq_cota_incrementa(self, auth_headers):
        from app.services.gemini import GeminiIndisponivel

        antes = client.get('/v1/ia/status', headers=auth_headers).json()['data']['provedores']['groq']['cota']['req_hoje']
        with patch('app.services.gemini._gerar', side_effect=GeminiIndisponivel('sem quota')):
            client.post('/v1/ia/resumir',
                        json={'titulo': 'Teste cota Groq', 'descricao': 'Descricao teste.'},
                        headers=auth_headers)
        depois = client.get('/v1/ia/status', headers=auth_headers).json()['data']['provedores']['groq']['cota']['req_hoje']
        assert depois > antes
