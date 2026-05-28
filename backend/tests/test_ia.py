"""
Testes do módulo IA Assistente (Gemini free tier).
Cobertura: endpoints /status, /resumir, /sugerir-descricao, /classificar-urgencia.
Os testes que chamam a API real do Gemini são marcados como skip quando
GEMINI_API_KEY não está configurada ou o pacote não está instalado.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini import _UsageTracker, get_uso

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
        resp = client.get('/v1/ia/status', headers=auth_headers)
        data = resp.json()['data']
        assert 'configurada' in data
        assert isinstance(data['configurada'], bool)

    def test_status_tem_campo_modelo(self, auth_headers):
        data = client.get('/v1/ia/status', headers=auth_headers).json()['data']
        assert 'modelo' in data
        assert data['modelo'] == 'gemini-2.0-flash'

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


# ---------------------------------------------------------------------------
# Tracker de cota (testa a lógica isolada sem chamar Gemini)
# ---------------------------------------------------------------------------

class TestUsageTracker:
    def test_tracker_inicia_zerado(self):
        tracker = _UsageTracker()
        snap = tracker.snapshot()
        assert snap['req_hoje'] == 0
        assert snap['req_ultimo_minuto'] == 0
        assert snap['restante_dia'] == 1500
        assert snap['restante_minuto'] == 15

    def test_registrar_incrementa_contadores(self):
        tracker = _UsageTracker()
        tracker.registrar()
        tracker.registrar()
        snap = tracker.snapshot()
        assert snap['req_hoje'] == 2
        assert snap['req_ultimo_minuto'] == 2
        assert snap['restante_dia'] == 1498
        assert snap['restante_minuto'] == 13

    def test_pct_calculado_corretamente(self):
        tracker = _UsageTracker()
        for _ in range(150):
            tracker.registrar()
        snap = tracker.snapshot()
        assert snap['pct_dia_usado'] == 10.0

    def test_get_uso_e_acessivel(self):
        snap = get_uso()
        assert isinstance(snap, dict)
        assert 'req_hoje' in snap


# ---------------------------------------------------------------------------
# POST /v1/ia/resumir — com mock do Gemini
# ---------------------------------------------------------------------------

class TestIAResumir:
    def test_resumir_sem_chave_retorna_503(self, auth_headers):
        with patch('app.api.ia.settings') as mock_settings:
            mock_settings.gemini_api_key = ''
            mock_settings.gemini_model = 'gemini-1.5-flash'
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
        assert 'resumo' in data
        assert data['resumo'] == 'Resumo gerado pelo mock.'

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
# Teste real Gemini (skip se chave não configurada)
# ---------------------------------------------------------------------------

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')


def _gemini_funcional() -> bool:
    """Retorna True somente se a chave existir e tiver quota > 0."""
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


_GEMINI_OK = _gemini_funcional()


@pytest.mark.skipif(not _GEMINI_OK, reason='GEMINI_API_KEY não configurada ou sem quota')
class TestGeminiReal:
    def test_sugerir_descricao_retorna_texto(self, auth_headers):
        resp = client.post('/v1/ia/sugerir-descricao',
                           json={'titulo': 'Validacao de CPF no cadastro', 'area': 'Credito', 'sistema': 'Portal Rural'},
                           headers=auth_headers)
        assert resp.status_code == 200
        descricao = resp.json()['data']['descricao_sugerida']
        assert len(descricao) > 20

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
