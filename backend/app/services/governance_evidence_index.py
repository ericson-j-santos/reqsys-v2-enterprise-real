from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_PATH = Path(__file__).resolve().parents[3] / 'docs' / 'ops-dashboard' / 'data' / 'governance-evidence-index.json'

_STATUS_SEVERITY = {
    'implemented': 'healthy',
    'dry_run': 'attention',
    'pending': 'attention',
    'unknown': 'attention',
}


def _fallback_index() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'overall_status': 'unknown',
        'governance_evidence_score': 0,
        'summary': {
            'total_capabilities': 0,
            'implemented_capabilities': 0,
            'dashboard_ready_capabilities': 0,
            'next_increment': 'surface_governance_evidence_cards_in_runtime_dashboard',
        },
        'evidence': [],
        'links': {},
        'runtime_dashboard_contract': {
            'card_fields': ['title', 'workflow', 'status', 'artifact', 'dashboard_ready'],
            'drilldown_fields': ['links', 'json_path', 'drilldown_fields'],
            'refresh_strategy': 'static_json_until_artifact_ingestion_is_enabled',
        },
    }


def carregar_governance_evidence_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return _fallback_index()
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_index()
    return payload if isinstance(payload, dict) else _fallback_index()


def status_para_severidade(status: str | None) -> str:
    return _STATUS_SEVERITY.get(str(status or '').lower(), 'attention')


def mapear_cards_governance(index: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in index.get('evidence') or []:
        if not item.get('dashboard_ready'):
            continue
        cards.append(
            {
                'id': f"governance-{item.get('id')}",
                'title': item.get('title') or item.get('id'),
                'type': 'governance_evidence',
                'value': item.get('status') or 'unknown',
                'severity': status_para_severidade(item.get('status')),
                'workflow': item.get('workflow'),
                'artifact': item.get('artifact'),
                'json_path': item.get('json_path'),
                'dashboard_ready': bool(item.get('dashboard_ready')),
                'latest_run': (item.get('links') or {}).get('latest_run'),
                'drilldown_fields': item.get('drilldown_fields') or [],
                'links': item.get('links') or {},
                'spa_drilldown': {
                    'path': '/monitoramento-operacional',
                    'query': {'secao': 'governanca', 'capability': item.get('id')},
                },
            }
        )
    return cards


def mapear_secao_governance(index: dict[str, Any]) -> dict[str, Any]:
    summary = index.get('summary') or {}
    return {
        'id': 'governance-evidence',
        'title': 'Governanca e Evidencias',
        'type': 'governance_cards',
        'items': {
            'overall_status': index.get('overall_status'),
            'governance_evidence_score': index.get('governance_evidence_score'),
            'summary': summary,
            'evidence': index.get('evidence') or [],
            'links': index.get('links') or {},
            'contract': index.get('runtime_dashboard_contract') or {},
        },
    }
