from __future__ import annotations

from app.services.trilha_d_history_index import (
    carregar_trilha_d_history_index,
    mapear_cards_trilha_d,
    mapear_secao_trilha_d,
    state_para_severidade,
    trend_para_severidade,
)


def test_carregar_trilha_d_history_index_expoe_historico():
    index = carregar_trilha_d_history_index()

    assert index['schema_version'] == '1.0.0'
    assert index['current_score'] >= 80
    assert index['history']
    assert index['dimension_summary']


def test_mapear_cards_trilha_d_inclui_score_e_dimensoes():
    index = carregar_trilha_d_history_index()
    cards = mapear_cards_trilha_d(index)

    assert cards
    assert cards[0]['id'] == 'trilha-d-score'
    assert any(card['id'] == 'trilha-d-dim-coverage' for card in cards)
    assert all(card['type'].startswith('trilha_d') for card in cards)


def test_mapear_secao_trilha_d_expoe_serie_historica():
    index = carregar_trilha_d_history_index()
    section = mapear_secao_trilha_d(index)

    assert section['id'] == 'trilha-d-history'
    assert section['type'] == 'trilha_d_history'
    assert section['items']['history']
    assert section['items']['dimension_summary']


def test_severidade_mapeia_estados_conhecidos():
    assert trend_para_severidade('improving') == 'healthy'
    assert trend_para_severidade('regressing') == 'unhealthy'
    assert state_para_severidade('green') == 'healthy'
    assert state_para_severidade('failed') == 'unhealthy'
