from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_PATH = (
    Path(__file__).resolve().parents[3]
    / 'docs'
    / 'ops-dashboard'
    / 'data'
    / 'continuous-trilha-d-monitoring-history.json'
)


def _fallback_index() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'state': 'unknown',
        'summary': {
            'continuous_trilha_d_monitoring_history_enabled': False,
            'samples': 0,
            'green_rate': 0.0,
            'avg_alerts_active': 0.0,
            'monitoring_stabilized': False,
            'recommendation': 'aguardar_artifact_ingestion',
        },
        'metrics': {},
        'history': [],
        'links': {},
        'runtime_dashboard_contract': {
            'card_fields': ['state', 'green_rate', 'avg_alerts_active', 'samples'],
            'refresh_strategy': 'static_json_until_artifact_ingestion_is_enabled',
        },
    }


def carregar_continuous_trilha_d_monitoring_history_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return _fallback_index()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_index()
    return payload if isinstance(payload, dict) else _fallback_index()
