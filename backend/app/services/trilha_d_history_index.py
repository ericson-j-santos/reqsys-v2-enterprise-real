from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_PATH = Path(__file__).resolve().parents[3] / 'docs' / 'ops-dashboard' / 'data' / 'trilha-d-history.json'

_TREND_SEVERITY = {
    'improving': 'healthy',
    'stable': 'attention',
    'regressing': 'unhealthy',
}

_STATE_SEVERITY = {
    'green': 'healthy',
    'yellow': 'attention',
    'failed': 'unhealthy',
}


def _fallback_index() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'state': 'unknown',
        'current_score': 0,
        'baseline_score': 0,
        'delta_from_baseline': 0,
        'trend': 'stable',
        'summary': {
            'samples': 0,
            'green_samples': 0,
            'failed_samples': 0,
            'next_increment': 'surface_trilha_d_history_in_ops_dashboard',
        },
        'dimension_summary': {},
        'history': [],
        'links': {},
        'runtime_dashboard_contract': {
            'card_fields': ['state', 'current_score', 'trend', 'delta_from_baseline'],
            'series_fields': ['timestamp', 'average_score', 'state'],
            'dimension_fields': ['current_status', 'current_score', 'trend', 'delta_from_baseline'],
            'refresh_strategy': 'static_json_until_artifact_ingestion_is_enabled',
        },
    }


def carregar_trilha_d_history_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return _fallback_index()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_index()
    return payload if isinstance(payload, dict) else _fallback_index()


def trend_para_severidade(trend: str | None) -> str:
    return _TREND_SEVERITY.get(str(trend or '').lower(), 'attention')


def state_para_severidade(state: str | None) -> str:
    return _STATE_SEVERITY.get(str(state or '').lower(), 'attention')


def mapear_cards_trilha_d(index: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = [
        {
            'id': 'trilha-d-score',
            'title': 'Trilha D Score',
            'type': 'trilha_d_history',
            'value': index.get('current_score', 0),
            'unit': 'score',
            'min': 0,
            'max': 100,
            'severity': state_para_severidade(index.get('state')),
            'trend': index.get('trend'),
            'delta_from_baseline': index.get('delta_from_baseline'),
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'trilha-d'},
            },
        }
    ]
    for dimension, summary in (index.get('dimension_summary') or {}).items():
        cards.append(
            {
                'id': f'trilha-d-dim-{dimension}',
                'title': f'Trilha D — {dimension}',
                'type': 'trilha_d_dimension',
                'value': summary.get('current_score', 0),
                'unit': 'score',
                'status': summary.get('current_status'),
                'severity': trend_para_severidade(summary.get('trend')),
                'trend': summary.get('trend'),
                'delta_from_baseline': summary.get('delta_from_baseline'),
                'spa_drilldown': {
                    'path': '/monitoramento-operacional',
                    'query': {'secao': 'trilha-d', 'dimensao': dimension},
                },
            }
        )
    return cards


def mapear_secao_trilha_d(index: dict[str, Any]) -> dict[str, Any]:
    summary = index.get('summary') or {}
    return {
        'id': 'trilha-d-history',
        'title': 'Historico Trilha D',
        'type': 'trilha_d_history',
        'items': {
            'state': index.get('state'),
            'current_score': index.get('current_score'),
            'baseline_score': index.get('baseline_score'),
            'delta_from_baseline': index.get('delta_from_baseline'),
            'trend': index.get('trend'),
            'summary': summary,
            'dimension_summary': index.get('dimension_summary') or {},
            'history': index.get('history') or [],
            'links': index.get('links') or {},
            'contract': index.get('runtime_dashboard_contract') or {},
        },
    }
