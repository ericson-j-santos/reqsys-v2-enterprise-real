"""Contrato HTTP do dashboard da coleta governada."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_coleta_requisitos_retorna_contrato_auditavel():
    resposta = client.get('/v1/dashboard/coleta-requisitos?janela_dias=30')

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo['success'] is True
    dados = corpo['data']
    assert dados['schema_version'] == '1.0.0'
    assert dados['janela_dias'] == 30
    assert isinstance(dados['coletas_total'], int)
    assert isinstance(dados['avaliacoes_total'], int)
    assert isinstance(dados['requisitos_gerados'], int)
    assert isinstance(dados['em_refinamento'], int)
    assert isinstance(dados['origens'], list)
    assert isinstance(dados['principais_pendencias'], list)
    assert 'nota_dados' in dados


def test_dashboard_coleta_requisitos_rejeita_janela_fora_do_contrato():
    resposta = client.get('/v1/dashboard/coleta-requisitos?janela_dias=0')

    assert resposta.status_code == 422
