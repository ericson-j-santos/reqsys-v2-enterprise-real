from app.services.autonomous_delivery_cycle_card import (
    carregar_autonomous_delivery_cycle_card,
    mapear_cards_autonomous_cycle,
    mapear_secao_autonomous_cycle,
    risco_para_severidade,
    status_para_severidade,
)


def test_carregar_autonomous_delivery_cycle_card_expoe_metricas():
    card = carregar_autonomous_delivery_cycle_card()
    assert card['card'] == 'autonomous_delivery_cycle'
    assert 'metrics' in card
    assert card['metrics']['candidate_count'] >= 0


def test_mapear_cards_autonomous_cycle_inclui_status_e_contadores():
    card = carregar_autonomous_delivery_cycle_card()
    cards = mapear_cards_autonomous_cycle(card)
    ids = {item['id'] for item in cards}
    assert {'autonomous-cycle-status', 'autonomous-cycle-candidates', 'autonomous-cycle-eligible', 'autonomous-cycle-merged'} <= ids
    assert all(item['type'] == 'autonomous_delivery_cycle' for item in cards)


def test_mapear_secao_autonomous_cycle_expoe_design_e_fila():
    card = carregar_autonomous_delivery_cycle_card()
    section = mapear_secao_autonomous_cycle(card)
    assert section['id'] == 'autonomous-delivery-cycle'
    assert section['items']['summary']
    assert 'design' in section['items']
    assert 'queue' in section['items']


def test_severidades_autonomous_cycle():
    assert status_para_severidade('passed') == 'healthy'
    assert status_para_severidade('post_merge_attention_required') == 'unhealthy'
    assert risco_para_severidade('high') == 'unhealthy'
