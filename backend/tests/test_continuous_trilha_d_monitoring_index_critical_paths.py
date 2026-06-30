"""Caminhos críticos — continuous trilha D monitoring index."""

from __future__ import annotations

import json

import app.services.continuous_trilha_d_monitoring_index as module
from app.services.continuous_trilha_d_monitoring_index import (
    carregar_continuous_trilha_d_monitoring_index,
    mapear_cards_continuous_monitoring,
    mapear_secao_continuous_monitoring,
    state_para_severidade,
)


def test_carregar_fallback_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'INDEX_PATH', tmp_path / 'ausente.json')
    index = carregar_continuous_trilha_d_monitoring_index()
    assert index['state'] == 'unknown'
    assert index['monitoring_enabled'] is False
    assert index['summary']['recommendation'] == 'aguardar_artifact_ingestion'


def test_carregar_fallback_quando_json_invalido(monkeypatch, tmp_path):
    path = tmp_path / 'continuous-trilha-d-monitoring.json'
    path.write_text('{bad', encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_continuous_trilha_d_monitoring_index()
    assert index['alerts'] == []


def test_carregar_fallback_quando_payload_nao_e_dict(monkeypatch, tmp_path):
    path = tmp_path / 'continuous-trilha-d-monitoring.json'
    path.write_text(json.dumps(None), encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_continuous_trilha_d_monitoring_index()
    assert index['alerts_active'] == 0


def test_mapear_cards_e_secao_com_alertas():
    index = {
        'state': 'yellow',
        'monitoring_enabled': True,
        'regression_alert': True,
        'alerts_active': 2,
        'alerts': [{'code': 'regression_predicted', 'severity': 'critical', 'message': 'teste'}],
        'summary': {'recommendation': 'investigar_alertas'},
        'signals': {'trend': 'regressing'},
    }
    cards = mapear_cards_continuous_monitoring(index)
    section = mapear_secao_continuous_monitoring(index)
    assert cards[0]['severity'] == 'attention'
    assert cards[0]['regression_alert'] is True
    assert section['items']['alerts'][0]['code'] == 'regression_predicted'


def test_state_para_severidade_mapeia_red():
    assert state_para_severidade('red') == 'unhealthy'
    assert state_para_severidade('') == 'attention'
