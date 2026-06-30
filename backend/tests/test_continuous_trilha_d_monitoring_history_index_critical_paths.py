"""Caminhos críticos — continuous trilha D monitoring history index."""

from __future__ import annotations

import json

import app.services.continuous_trilha_d_monitoring_history_index as module
from app.services.continuous_trilha_d_monitoring_history_index import (
    carregar_continuous_trilha_d_monitoring_history_index,
    mapear_cards_continuous_monitoring_history,
    mapear_secao_continuous_monitoring_history,
    state_para_severidade,
)


def test_carregar_fallback_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'INDEX_PATH', tmp_path / 'ausente.json')
    index = carregar_continuous_trilha_d_monitoring_history_index()
    assert index['summary']['continuous_trilha_d_monitoring_history_enabled'] is False


def test_mapear_cards_e_secao_expoem_estabilidade():
    index = {
        'state': 'green',
        'summary': {
            'samples': 3,
            'green_rate': 1.0,
            'avg_alerts_active': 0.0,
            'monitoring_stabilized': True,
            'continuous_trilha_d_monitoring_history_enabled': True,
        },
        'metrics': {'samples': 3},
        'history': [{'timestamp': '2026-06-30T00:00:00Z', 'state': 'green', 'alerts_active': 0}],
        'links': {},
    }
    cards = mapear_cards_continuous_monitoring_history(index)
    section = mapear_secao_continuous_monitoring_history(index)
    assert cards[0]['monitoring_stabilized'] is True
    assert cards[0]['spa_drilldown']['query']['secao'] == 'trilha-d-monitoring-history'
    assert section['items']['summary']['monitoring_stabilized'] is True


def test_state_para_severidade_mapeia_red():
    assert state_para_severidade('red') == 'unhealthy'


def test_carregar_json_valido(monkeypatch, tmp_path):
    path = tmp_path / 'continuous-trilha-d-monitoring-history.json'
    path.write_text(
        json.dumps(
            {
                'state': 'green',
                'summary': {'samples': 1, 'continuous_trilha_d_monitoring_history_enabled': True},
                'history': [],
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_continuous_trilha_d_monitoring_history_index()
    assert index['summary']['samples'] == 1
