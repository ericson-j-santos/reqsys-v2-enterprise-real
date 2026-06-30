from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import operational_mesh_signal as mesh_service


def test_fallback_signal_quando_artifact_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mesh_service, 'SIGNAL_CANDIDATES', [Path('/tmp/inexistente-signal.json')])
    payload = mesh_service.carregar_operational_mesh_signal()
    assert payload['hydrated'] is False
    assert payload['mesh_integrated'] is False


def test_mapear_cards_operational_mesh_integrado() -> None:
    signal = {
        'overall_state': 'green',
        'mesh_integrated': True,
        'maturity_percent': 92.5,
        'evidence_gate_consolidated': {'consolidated': True, 'state': 'green', 'layers_available': 3},
        'cross_runtime_analytics': {'unified_score': 88, 'sources_hydrated': 4},
    }
    cards = mesh_service.mapear_cards_operational_mesh(signal)
    ids = {card['id'] for card in cards}
    assert {'operational-mesh-integrated', 'operational-mesh-maturity', 'evidence-gate-consolidated', 'cross-runtime-score'} <= ids


def test_mapear_secao_operational_mesh_timeline() -> None:
    signal = {
        'overall_state': 'green',
        'mesh_integrated': True,
        'operational_mesh': {
            'hub': {'available': True, 'state': 'green', 'detail': 'ok'},
            'alert_intelligence': {'available': True, 'state': 'green', 'detail': 'ok'},
            'event_bus': {'available': True, 'state': 'green', 'detail': 'ok'},
            'chain': 'mesh → alert → bus',
        },
        'evidence_gate_consolidated': {'consolidated': True},
        'cross_runtime_analytics': {'unified_score': 90},
    }
    section = mesh_service.mapear_secao_operational_mesh(signal)
    assert section['id'] == 'operational-mesh-chain'
    assert len(section['items']['timeline']) == 4


def test_runtime_operational_mesh_endpoint() -> None:
    res = TestClient(app).get('/api/runtime/operational-mesh', headers={'X-Correlation-ID': 'corr-mesh-test'})
    assert res.status_code == 200
    body = res.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == 'corr-mesh-test'
    assert 'signal' in body['data']
    assert 'cards' in body['data']
    assert body['data']['section']['id'] == 'operational-mesh-chain'


def test_runtime_dashboard_inclui_malha_operacional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    signal_dir = tmp_path / 'artifacts/unified-operational-signal-consolidator'
    signal_dir.mkdir(parents=True)
    (signal_dir / 'unified-operational-signal.json').write_text(
        json.dumps(
            {
                'overall_state': 'green',
                'mesh_integrated': True,
                'maturity_percent': 95.0,
                'correlation_id': 'corr-mesh-fixture',
                'evidence_gate_consolidated': {'consolidated': True, 'state': 'green', 'layers_available': 3},
                'cross_runtime_analytics': {'unified_score': 91, 'sources_hydrated': 4, 'mode': 'cross_runtime_consolidated'},
                'operational_mesh': {
                    'hub': {'available': True, 'state': 'green', 'detail': 'ACTIVE'},
                    'alert_intelligence': {'available': True, 'state': 'green', 'detail': 'INFO'},
                    'event_bus': {'available': True, 'state': 'green', 'detail': 'ops.signal'},
                    'chain': 'mesh_hub → alert_intelligence → event_bus → signal_consolidator',
                },
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(mesh_service, 'SIGNAL_CANDIDATES', [signal_dir / 'unified-operational-signal.json'])

    res = TestClient(app).get('/api/runtime/dashboard')
    data = res.json()['data']
    assert data['schema_version'] == '1.4.0'
    assert data['operational_mesh']['mesh_integrated'] is True
    assert 'operational-mesh-chain' in {section['id'] for section in data['sections']}
    card_ids = {card['id'] for card in data['cards']}
    assert 'operational-mesh-integrated' in card_ids
    assert 'cross-runtime-score' in card_ids
