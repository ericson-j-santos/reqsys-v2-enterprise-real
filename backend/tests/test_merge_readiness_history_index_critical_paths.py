"""Caminhos críticos — merge readiness history index."""

from __future__ import annotations

import json

import app.services.merge_readiness_history_index as module
from app.services.merge_readiness_history_index import (
    carregar_merge_readiness_history_index,
    mapear_cards_merge_readiness_history,
    mapear_secao_merge_readiness_history,
    state_para_severidade,
)


def test_carregar_fallback_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'INDEX_PATH', tmp_path / 'ausente.json')
    index = carregar_merge_readiness_history_index()
    assert index['summary']['merge_readiness_history_enabled'] is False


def test_mapear_cards_e_secao_expoem_estabilidade():
    index = {
        'state': 'green',
        'summary': {
            'samples': 3,
            'blocked_rate': 0.0,
            'avg_changed_files': 6.0,
            'merge_readiness_stabilized': True,
            'merge_readiness_history_enabled': True,
        },
        'metrics': {'samples': 3},
        'history': [{'timestamp': '2026-06-30T00:00:00Z', 'status': 'ready', 'changed_files': 5}],
        'links': {},
    }
    cards = mapear_cards_merge_readiness_history(index)
    section = mapear_secao_merge_readiness_history(index)
    assert cards[0]['merge_readiness_stabilized'] is True
    assert cards[0]['spa_drilldown']['query']['secao'] == 'merge-readiness-history'
    assert section['items']['summary']['merge_readiness_stabilized'] is True


def test_state_para_severidade_mapeia_red():
    assert state_para_severidade('red') == 'unhealthy'


def test_carregar_json_valido(monkeypatch, tmp_path):
    path = tmp_path / 'merge-readiness-history.json'
    path.write_text(
        json.dumps(
            {
                'state': 'green',
                'summary': {'samples': 1, 'merge_readiness_history_enabled': True},
                'history': [],
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_merge_readiness_history_index()
    assert index['summary']['samples'] == 1
