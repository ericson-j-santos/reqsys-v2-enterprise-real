from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CARD_PATH = (
    Path(__file__).resolve().parents[3]
    / 'docs'
    / 'ops-dashboard'
    / 'data'
    / 'autonomous-delivery-cycle-dashboard-card.json'
)

_RISK_SEVERITY = {
    'low': 'healthy',
    'medium': 'attention',
    'high': 'unhealthy',
}

_STATUS_SEVERITY = {
    'passed': 'healthy',
    'seed': 'attention',
    'post_merge_attention_required': 'unhealthy',
    'blocked': 'unhealthy',
}


def _fallback_card() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'card': 'autonomous_delivery_cycle',
        'status': 'seed',
        'risk': 'medium',
        'summary': 'Ciclo governado de auto-merge condicionado a CI verde, labels explicitas e fila report-only.',
        'metrics': {
            'candidate_count': 0,
            'eligible_count': 0,
            'merged_count': 0,
            'blocker_count': 0,
            'next_increment_queue_count': 0,
        },
        'latest': {'mode': 'seed', 'required_label': 'cycle:auto-merge-approved', 'max_prs': 1},
        'queue': {'status': 'empty_seed', 'items': []},
        'links': {},
        'design': {
            'trilha_c_reference': 'docs/adr/ADR-038-trilha-c-ux-operacional.md',
            'spa_surface': '/monitoramento-operacional?secao=autonomous-cycle',
            'figma_github_route': '/figma-github',
        },
        'guardrails': ['offline_static_generation', 'queue_is_report_only'],
    }


def carregar_autonomous_delivery_cycle_card() -> dict[str, Any]:
    if not CARD_PATH.exists():
        return _fallback_card()
    try:
        payload = json.loads(CARD_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _fallback_card()
    return payload if isinstance(payload, dict) else _fallback_card()


def risco_para_severidade(risk: str | None) -> str:
    return _RISK_SEVERITY.get(str(risk or '').lower(), 'attention')


def status_para_severidade(status: str | None) -> str:
    return _STATUS_SEVERITY.get(str(status or '').lower(), 'attention')


def mapear_cards_autonomous_cycle(card: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = card.get('metrics') or {}
    return [
        {
            'id': 'autonomous-cycle-status',
            'title': 'Autonomous Cycle',
            'type': 'autonomous_delivery_cycle',
            'value': card.get('status') or 'seed',
            'severity': status_para_severidade(card.get('status')),
            'risk': card.get('risk') or 'medium',
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'autonomous-cycle'},
            },
        },
        {
            'id': 'autonomous-cycle-candidates',
            'title': 'Candidatos',
            'type': 'autonomous_delivery_cycle',
            'value': metrics.get('candidate_count', 0),
            'unit': 'prs',
            'severity': risco_para_severidade(card.get('risk')),
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'autonomous-cycle'},
            },
        },
        {
            'id': 'autonomous-cycle-eligible',
            'title': 'Elegiveis',
            'type': 'autonomous_delivery_cycle',
            'value': metrics.get('eligible_count', 0),
            'unit': 'prs',
            'severity': risco_para_severidade(card.get('risk')),
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'autonomous-cycle'},
            },
        },
        {
            'id': 'autonomous-cycle-merged',
            'title': 'Mergeados',
            'type': 'autonomous_delivery_cycle',
            'value': metrics.get('merged_count', 0),
            'unit': 'prs',
            'severity': 'healthy' if metrics.get('merged_count', 0) else 'attention',
            'spa_drilldown': {
                'path': '/monitoramento-operacional',
                'query': {'secao': 'autonomous-cycle'},
            },
        },
    ]


def mapear_secao_autonomous_cycle(card: dict[str, Any]) -> dict[str, Any]:
    metrics = card.get('metrics') or {}
    design = card.get('design') or {}
    links = card.get('links') or {}
    return {
        'id': 'autonomous-delivery-cycle',
        'title': 'Autonomous Delivery Cycle',
        'type': 'autonomous_delivery_cycle_card',
        'items': {
            'status': card.get('status'),
            'risk': card.get('risk'),
            'summary': card.get('summary'),
            'metrics': metrics,
            'latest': card.get('latest') or {},
            'queue': card.get('queue') or {},
            'links': links,
            'design': design,
            'guardrails': card.get('guardrails') or [],
        },
    }
