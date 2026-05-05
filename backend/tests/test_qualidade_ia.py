from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestQualidadeIA:
    def test_resumo_retorna_200(self):
        resp = client.get('/v1/qualidade-ia/resumo')
        assert resp.status_code == 200

    def test_resumo_contem_score_e_metricas(self):
        resp = client.get('/v1/qualidade-ia/resumo')
        data = resp.json()['data']
        assert 'score_geral' in data
        assert isinstance(data['metricas'], dict)
        assert 'seguranca' in data['metricas']

    def test_resumo_tem_tendencia_lista(self):
        resp = client.get('/v1/qualidade-ia/resumo')
        data = resp.json()['data']
        assert 'tendencia' in data
        assert isinstance(data['tendencia'], list)

    def test_snapshot_retorna_200(self):
        resp = client.post('/v1/qualidade-ia/snapshot')
        assert resp.status_code == 200

    def test_snapshot_retorna_id(self):
        resp = client.post('/v1/qualidade-ia/snapshot')
        data = resp.json()['data']
        assert 'id' in data
        assert data['id'] > 0

    def test_tendencia_respeita_limit(self):
        resp = client.get('/v1/qualidade-ia/tendencia?limit=3')
        data = resp.json()['data']
        assert data['limit'] == 3
        assert len(data['itens']) <= 3

    def test_export_csv_retorna_200(self):
        resp = client.get('/v1/qualidade-ia/tendencia.csv?limit=5')
        assert resp.status_code == 200
        assert 'text/csv' in resp.headers['content-type']

    def test_export_pdf_retorna_200(self):
        resp = client.get('/v1/qualidade-ia/tendencia.pdf?limit=5')
        assert resp.status_code == 200
        assert 'application/pdf' in resp.headers['content-type']

    def test_export_csv_com_filtro_7_dias(self):
        # Criar snapshot para garantir que há dados
        client.post('/v1/qualidade-ia/snapshot')
        resp = client.get('/v1/qualidade-ia/tendencia.csv?dias=7')
        assert resp.status_code == 200
        assert 'text/csv' in resp.headers['content-type']
        # O nome do arquivo deve conter o período
        cd = resp.headers.get('content-disposition', '')
        assert '7d' in cd

    def test_export_pdf_com_filtro_30_dias(self):
        client.post('/v1/qualidade-ia/snapshot')
        resp = client.get('/v1/qualidade-ia/tendencia.pdf?dias=30')
        assert resp.status_code == 200
        assert 'application/pdf' in resp.headers['content-type']
        cd = resp.headers.get('content-disposition', '')
        assert '30d' in cd

    def test_tendencia_retorna_campo_dias_no_payload(self):
        resp = client.get('/v1/qualidade-ia/tendencia?dias=90')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['dias'] == 90
        assert isinstance(data['itens'], list)
