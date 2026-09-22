from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_PATH = (
    Path(__file__).resolve().parents[3]
    / 'docs'
    / 'ops-dashboard'
    / 'data'
    / 'continuous-trilha-d-monitoring.json'
)

_STATE_SEVERITY = {
    'green': 'healthy',
    'yellow': 'attention',
    'red': 'unhealthy',
    'unknown': 'attention',
}


def _fallback_index() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'state': 'unknown',
        'monitoring_enabled': False,
        'regression_alert': False,
        'alerts_active': 0,
        'signals': {},
        'alerts': [],
        'summary': {
            'continuous_monitoring_enabled': False,
            'recommendation': 'aguardar_artifact_ingestion',
        },
        'links': {},
        'runtime_dashboard_contract': {
            'card_fields': ['state', 'monitoring_enabled', 'regression_alert', 'alerts_active'],
            'refresh_strategy': 'static_json_until_artifact_ingestion_is_enabled',
        },
    }


def carregar_continuous_trilha_d_monitoring_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return _fallback_index()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_index()
    return payload if isinstance(payload, dict) else _fallback_index()


def state_para_severidade(state: str | None) -> str:
    return _STATE_SEVERITY.get(str(state or '').lower(), 'attention')


def mapear_cards_continuous_monitoring(index: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            'id': 'continuous-trilha-d-monitoring',
            'title': 'Monitoramento Contínuo Trilha D',
            'type': 'continuous_trilha_d_monitoring',
            'value': index.get('alerts_active', 0),
            'unit': 'alertas',
            'severity': state_para_severidade(index.get('state')),
            'monitoring_enabled': index.get('monitoring_enabled'),
            'regression_alert': index.get('regression_alert'),
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'trilha-d-monitoring'},
            },
        }
    ]


def mapear_secao_continuous_monitoring(index: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': 'continuous-trilha-d-monitoring',
        'title': 'Monitoramento Contínuo Trilha D',
        'type': 'continuous_trilha_d_monitoring',
        'items': {
            'state': index.get('state'),
            'monitoring_enabled': index.get('monitoring_enabled'),
            'regression_alert': index.get('regression_alert'),
            'alerts_active': index.get('alerts_active'),
            'signals': index.get('signals') or {},
            'alerts': index.get('alerts') or [],
            'summary': index.get('summary') or {},
            'links': index.get('links') or {},
            'contract': index.get('runtime_dashboard_contract') or {},
        },
    }
