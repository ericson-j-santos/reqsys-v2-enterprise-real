"""Caminhos críticos — governance evidence index (fallback e mapeamento)."""

from __future__ import annotations

import json

import app.services.governance_evidence_index as module
from app.services.governance_evidence_index import (
    carregar_governance_evidence_index,
    mapear_cards_governance,
    mapear_secao_governance,
    status_para_severidade,
)


def test_carregar_fallback_quando_arquivo_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'INDEX_PATH', tmp_path / 'ausente.json')
    index = carregar_governance_evidence_index()
    assert index['overall_status'] == 'unknown'
    assert index['summary']['next_increment'] == 'surface_governance_evidence_cards_in_runtime_dashboard'


def test_carregar_fallback_quando_json_invalido(monkeypatch, tmp_path):
    path = tmp_path / 'governance-evidence-index.json'
    path.write_text('{invalid', encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_governance_evidence_index()
    assert index['governance_evidence_score'] == 0


def test_carregar_fallback_quando_payload_nao_e_dict(monkeypatch, tmp_path):
    path = tmp_path / 'governance-evidence-index.json'
    path.write_text(json.dumps(['lista']), encoding='utf-8')
    monkeypatch.setattr(module, 'INDEX_PATH', path)
    index = carregar_governance_evidence_index()
    assert index['evidence'] == []


def test_mapear_cards_ignora_itens_sem_dashboard_ready():
    index = {
        'evidence': [
            {'id': 'oculto', 'dashboard_ready': False, 'status': 'implemented'},
            {
                'id': 'visivel',
                'dashboard_ready': True,
                'status': 'dry_run',
                'title': 'Capacidade visível',
                'links': {'latest_run': 'https://example.com/run/1'},
            },
        ]
    }
    cards = mapear_cards_governance(index)
    assert len(cards) == 1
    assert cards[0]['id'] == 'governance-visivel'
    assert cards[0]['severity'] == 'attention'


def test_status_para_severidade_desconhecido():
    assert status_para_severidade('pending') == 'attention'
    assert status_para_severidade(None) == 'attention'


def test_mapear_secao_governance_com_resumo_vazio():
    section = mapear_secao_governance({'overall_status': 'green', 'governance_evidence_score': 90})
    assert section['items']['summary'] == {}
