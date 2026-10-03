from __future__ import annotations

from app.services.governance_evidence_index import (
    carregar_governance_evidence_index,
    mapear_cards_governance,
    mapear_secao_governance,
    status_para_severidade,
)


def test_carregar_governance_evidence_index_expoe_capacidades():
    index = carregar_governance_evidence_index()

    assert index['schema_version'] == '1.0.0'
    assert index['governance_evidence_score'] >= 80
    assert index['summary']['total_capabilities'] >= 4
    assert index['evidence']


def test_mapear_cards_governance_respeita_dashboard_ready():
    index = carregar_governance_evidence_index()
    cards = mapear_cards_governance(index)

    assert cards
    assert all(card['type'] == 'governance_evidence' for card in cards)
    assert all(card['dashboard_ready'] for card in cards)
    assert any(card['id'] == 'governance-conflict_prediction' for card in cards)
    assert all(card.get('latest_run') for card in cards)


def test_mapear_secao_governance_expoe_resumo():
    index = carregar_governance_evidence_index()
    section = mapear_secao_governance(index)

    assert section['id'] == 'governance-evidence'
    assert section['type'] == 'governance_cards'
    assert section['items']['governance_evidence_score'] == index['governance_evidence_score']
    assert section['items']['evidence']


def test_status_para_severidade_mapeia_estados_conhecidos():
    assert status_para_severidade('implemented') == 'healthy'
    assert status_para_severidade('dry_run') == 'attention'
    assert status_para_severidade('unknown') == 'attention'
