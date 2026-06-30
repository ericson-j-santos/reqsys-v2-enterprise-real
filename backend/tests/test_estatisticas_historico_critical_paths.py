"""Testes de caminhos críticos — serviço estatisticas_historico."""

import json

from app.services import estatisticas_historico as historico


def test_carregar_historico_retorna_vazio_quando_arquivo_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, 'HISTORY_PATH', tmp_path / 'inexistente.json')
    assert historico.carregar_historico() == []


def test_carregar_historico_ignora_json_invalido(tmp_path, monkeypatch):
    path = tmp_path / 'snapshots.json'
    path.write_text('{invalido', encoding='utf-8')
    monkeypatch.setattr(historico, 'HISTORY_PATH', path)
    assert historico.carregar_historico() == []


def test_carregar_historico_aceita_payload_com_chave_snapshots(tmp_path, monkeypatch):
    path = tmp_path / 'snapshots.json'
    path.write_text(
        json.dumps({'snapshots': [{'schema_version': '2.0.0', 'indicadores_resumo': []}]}),
        encoding='utf-8',
    )
    monkeypatch.setattr(historico, 'HISTORY_PATH', path)
    dados = historico.carregar_historico()
    assert len(dados) == 1
    assert dados[0]['schema_version'] == '2.0.0'


def test_registrar_snapshot_persiste_e_limita_historico(tmp_path, monkeypatch):
    path = tmp_path / 'snapshots.json'
    monkeypatch.setattr(historico, 'HISTORY_PATH', path)
    monkeypatch.setattr(historico, 'MAX_SNAPSHOTS', 2)

    for indice in range(3):
        historico.registrar_snapshot(
            {
                'schema_version': '2.0.0',
                'coletado_em': f'2026-06-30T10:0{indice}:00Z',
                'indicadores': [
                    {'id': 'req_abertos', 'valorAtual': indice, 'estadoAtual': 'ok', 'tendencia': 'estavel'}
                ],
            }
        )

    salvo = json.loads(path.read_text(encoding='utf-8'))
    assert len(salvo) == 2
    assert salvo[0]['resumo'] == {}
    assert salvo[-1]['indicadores_resumo'][0]['id'] == 'req_abertos'


def test_calcular_tendencias_compara_snapshots_consecutivos():
    historico_lista = [
        {'indicadores_resumo': [{'id': 'req_abertos', 'valorAtual': 10}]},
        {'indicadores_resumo': [{'id': 'req_abertos', 'valorAtual': 12}]},
        {'indicadores_resumo': [{'id': 'req_abertos', 'valorAtual': 8}]},
        {'indicadores_resumo': [{'id': 'req_abertos', 'valorAtual': 8}]},
    ]

    assert historico.calcular_tendencias(historico_lista[:1]) == {}
    assert historico.calcular_tendencias(historico_lista[:2]) == {'req_abertos': 'subindo'}
    assert historico.calcular_tendencias(historico_lista[:3]) == {'req_abertos': 'caindo'}
    assert historico.calcular_tendencias(historico_lista) == {'req_abertos': 'estavel'}


def test_registrar_snapshot_gera_coletado_em_quando_ausente(tmp_path, monkeypatch):
    path = tmp_path / 'snapshots.json'
    monkeypatch.setattr(historico, 'HISTORY_PATH', path)

    historico.registrar_snapshot({'indicadores': []})

    salvo = json.loads(path.read_text(encoding='utf-8'))
    assert salvo[0]['coletado_em']


def test_calcular_tendencias_ignora_indicador_ausente_no_snapshot_anterior():
    historico_lista = [
        {'indicadores_resumo': [{'id': 'antigo', 'valorAtual': 1}]},
        {'indicadores_resumo': [{'id': 'novo', 'valorAtual': 2}]},
    ]
    assert historico.calcular_tendencias(historico_lista) == {}


def test_calcular_tendencias_ignora_valores_nao_numericos():
    historico_lista = [
        {'indicadores_resumo': [{'id': 'indicador_x', 'valorAtual': 'n/a'}]},
        {'indicadores_resumo': [{'id': 'indicador_x', 'valorAtual': 'n/a'}]},
    ]
    assert historico.calcular_tendencias(historico_lista) == {}
