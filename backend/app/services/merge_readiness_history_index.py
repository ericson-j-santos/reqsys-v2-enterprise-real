from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_PATH = (
    Path(__file__).resolve().parents[3]
    / 'docs'
    / 'ops-dashboard'
    / 'data'
    / 'merge-readiness-history.json'
)


def _fallback_index() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'state': 'unknown',
        'summary': {
            'merge_readiness_history_enabled': False,
            'samples': 0,
            'blocked_rate': 0.0,
            'avg_changed_files': 0.0,
            'merge_readiness_stabilized': False,
            'recommendation': 'aguardar_merge_readiness_gate',
        },
        'metrics': {},
        'history': [],
        'links': {},
        'runtime_dashboard_contract': {
            'card_fields': ['state', 'blocked_rate', 'avg_changed_files', 'samples'],
            'refresh_strategy': 'merge_readiness_gate_artifact_ingest',
        },
    }


def carregar_merge_readiness_history_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return _fallback_index()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_index()
    return payload if isinstance(payload, dict) else _fallback_index()


_STATE_SEVERITY = {
    'green': 'healthy',
    'yellow': 'attention',
    'red': 'unhealthy',
    'unknown': 'attention',
}


def state_para_severidade(state: str | None) -> str:
    return _STATE_SEVERITY.get(str(state or '').lower(), 'attention')


def mapear_cards_merge_readiness_history(index: dict[str, Any]) -> list[dict[str, Any]]:
    summary = index.get('summary') or {}
    return [
        {
            'id': 'merge-readiness-history',
            'title': 'Merge Readiness — Histórico',
            'type': 'merge_readiness_history',
            'value': summary.get('samples', 0),
            'unit': 'amostras',
            'severity': state_para_severidade(index.get('state')),
            'merge_readiness_stabilized': bool(summary.get('merge_readiness_stabilized')),
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'merge-readiness-history'},
            },
        }
    ]


def mapear_secao_merge_readiness_history(index: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': 'merge-readiness-history',
        'title': 'Merge Readiness — Histórico',
        'type': 'merge_readiness_history',
        'items': {
            'state': index.get('state'),
            'summary': index.get('summary') or {},
            'metrics': index.get('metrics') or {},
            'latest_snapshot': index.get('latest_snapshot') or {},
            'history': index.get('history') or [],
            'links': index.get('links') or {},
            'contract': index.get('runtime_dashboard_contract') or {},
        },
    }
