"""Caminhos críticos — trilha D history index (fallback e mapeamento)."""

from __future__ import annotations

import json

import app.services.trilha_d_history_index as module
from app.services.trilha_d_history_index import (
    carregar_trilha_d_history_index,
    mapear_cards_trilha_d,
    mapear_secao_trilha_d,
    state_para_severidade,
    trend_para_severidade,
)


def test_carregar_fallback_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'INDEX_PATH', tmp_path / 'ausente.json')
    index = carregar_trilha_d_history_index()
    assert index['state'] == 'unknown'
    assert index['summary']['next_increment'] == 'surface_trilha_d_history_in_ops_dashboard'


def test_carregar_fallback_quando_json_invalido(monkeypatch, tmp_path):
    path = tmp_path / 'trilha-d-history.json'
    path.write_text('not-json', encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_trilha_d_history_index()
    assert index['current_score'] == 0


def test_carregar_fallback_quando_payload_nao_e_dict(monkeypatch, tmp_path):
    path = tmp_path / 'trilha-d-history.json'
    path.write_text(json.dumps(42), encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_trilha_d_history_index()
    assert index['history'] == []


def test_mapear_cards_inclui_dimensoes_customizadas():
    index = {
        'state': 'green',
        'current_score': 95,
        'trend': 'improving',
        'delta_from_baseline': 2,
        'dimension_summary': {
            'mutation': {'current_score': 100, 'current_status': 'passed', 'trend': 'stable', 'delta_from_baseline': 0},
        },
    }
    cards = mapear_cards_trilha_d(index)
    assert cards[0]['severity'] == 'healthy'
    assert any(card['id'] == 'trilha-d-dim-mutation' for card in cards)


def test_severidade_para_valores_desconhecidos():
    assert trend_para_severidade('volatile') == 'attention'
    assert state_para_severidade('yellow') == 'attention'


def test_mapear_secao_trilha_d_normaliza_campos_opcionais():
    section = mapear_secao_trilha_d({'state': 'yellow', 'current_score': 80})
    assert section['items']['history'] == []
    assert section['items']['links'] == {}
