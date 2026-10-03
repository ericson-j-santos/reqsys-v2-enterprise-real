import json
from pathlib import Path

import pytest

from app.services import continuous_trilha_d_monitoring_history_index as history_index
from app.services.continuous_trilha_d_monitoring_history_index import (
    carregar_continuous_trilha_d_monitoring_history_index,
)


def test_carregar_continuous_trilha_d_monitoring_history_index_expoe_summary():
    index = carregar_continuous_trilha_d_monitoring_history_index()
    assert 'summary' in index
    assert 'history' in index
    assert 'continuous_trilha_d_monitoring_history_enabled' in index['summary']


def test_carregar_index_usa_fallback_quando_arquivo_ausente(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(history_index, 'INDEX_PATH', tmp_path / 'ausente.json')

    payload = carregar_continuous_trilha_d_monitoring_history_index()

    assert payload['state'] == 'unknown'
    assert payload['summary']['continuous_trilha_d_monitoring_history_enabled'] is False


def test_carregar_index_usa_fallback_quando_json_invalido(monkeypatch, tmp_path: Path):
    invalid = tmp_path / 'invalid.json'
    invalid.write_text('{nao-json', encoding='utf-8')
    monkeypatch.setattr(history_index, 'INDEX_PATH', invalid)

    payload = carregar_continuous_trilha_d_monitoring_history_index()

    assert payload['state'] == 'unknown'


def test_carregar_index_usa_fallback_quando_payload_nao_e_dict(monkeypatch, tmp_path: Path):
    invalid = tmp_path / 'lista.json'
    invalid.write_text(json.dumps(['item']), encoding='utf-8')
    monkeypatch.setattr(history_index, 'INDEX_PATH', invalid)

    payload = carregar_continuous_trilha_d_monitoring_history_index()

    assert payload['state'] == 'unknown'
