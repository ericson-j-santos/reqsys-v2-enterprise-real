from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

SIGNAL_CANDIDATES = [
    ROOT / 'artifacts/unified-operational-signal-consolidator/unified-operational-signal.json',
]

ANALYTICS_CANDIDATES = [
    ROOT / 'reports/github-runtime-analytics/github-runtime-analytics.json',
]

_STATE_SEVERITY = {
    'green': 'healthy',
    'yellow': 'attention',
    'red': 'degraded',
    'unknown': 'attention',
}


def _fallback_signal() -> dict[str, Any]:
    return {
        'schema_version': '1.0.0',
        'source': 'operational-mesh-fallback',
        'status': 'unknown',
        'overall_state': 'unknown',
        'mesh_integrated': False,
        'maturity_percent': 0.0,
        'evidence_gate_consolidated': {
            'consolidated': False,
            'state': 'unknown',
            'layers_available': 0,
            'layers': [],
        },
        'cross_runtime_analytics': {
            'mode': 'unavailable',
            'sources_hydrated': 0,
            'sources_total': 4,
            'unified_score': 0,
        },
        'operational_mesh': {
            'hub': {'available': False, 'state': 'unknown'},
            'alert_intelligence': {'available': False, 'state': 'unknown'},
            'event_bus': {'available': False, 'state': 'unknown'},
            'chain': 'mesh_hub → alert_intelligence → event_bus → signal_consolidator',
        },
        'hydrated': False,
        'next_increment': 'executar_unified_operational_signal_consolidator',
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _resolve_first(candidates: list[Path]) -> tuple[dict[str, Any] | None, str | None]:
    for path in candidates:
        payload = _load_json(path)
        if payload is not None:
            return payload, _relative_path(path)
    return None, None


def estado_mesh_para_severidade(state: str | None) -> str:
    return _STATE_SEVERITY.get(str(state or 'unknown').lower(), 'attention')


def carregar_operational_mesh_signal() -> dict[str, Any]:
    payload, source_path = _resolve_first(SIGNAL_CANDIDATES)
    if not payload:
        return _fallback_signal()
    return {
        **payload,
        'hydrated': True,
        'artifact_path': source_path,
    }


def carregar_cross_runtime_analytics_report() -> dict[str, Any]:
    payload, source_path = _resolve_first(ANALYTICS_CANDIDATES)
    if not payload:
        signal = carregar_operational_mesh_signal()
        return {
            'hydrated': bool(signal.get('hydrated')),
            'runtime_state': 'ANALYTICS_PARTIAL',
            'artifact_path': None,
            'unified_score': (signal.get('cross_runtime_analytics') or {}).get('unified_score', 0),
            'sources_hydrated': (signal.get('cross_runtime_analytics') or {}).get('sources_hydrated', 0),
            'mode': (signal.get('cross_runtime_analytics') or {}).get('mode', 'signal_fallback'),
        }
    return {**payload, 'hydrated': True, 'artifact_path': source_path}


def _spa_drilldown(path: str, query: dict | None = None) -> dict[str, Any]:
    return {'path': path, 'query': query or {}}


def mapear_cards_operational_mesh(signal: dict[str, Any]) -> list[dict[str, Any]]:
    analytics = signal.get('cross_runtime_analytics') or {}
    evidence = signal.get('evidence_gate_consolidated') or {}
    maturity = float(signal.get('maturity_percent') or 0)
    unified_score = int(analytics.get('unified_score') or 0)
    mesh_integrated = bool(signal.get('mesh_integrated'))
    evidence_ok = bool(evidence.get('consolidated'))

    return [
        {
            'id': 'operational-mesh-integrated',
            'title': 'Malha Operacional',
            'type': 'operational_mesh',
            'value': 'integrated' if mesh_integrated else 'partial',
            'severity': 'healthy' if mesh_integrated else 'attention',
            'unit': 'status',
            'drilldown': '/api/runtime/operational-mesh',
            'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'malha-operacional'}),
        },
        {
            'id': 'operational-mesh-maturity',
            'title': 'Maturidade Mesh',
            'type': 'metric',
            'value': round(maturity, 1),
            'unit': 'percent',
            'min': 0,
            'max': 100,
            'severity': estado_mesh_para_severidade(signal.get('overall_state')),
            'drilldown': '/api/runtime/operational-mesh',
            'spa_drilldown': _spa_drilldown('/analytics', {'secao': 'malha-operacional'}),
        },
        {
            'id': 'evidence-gate-consolidated',
            'title': 'Evidence Gate',
            'type': 'operational_mesh',
            'value': 'consolidated' if evidence_ok else 'partial',
            'severity': estado_mesh_para_severidade(evidence.get('state')),
            'layers_available': evidence.get('layers_available', 0),
            'drilldown': '/api/runtime/operational-mesh',
            'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'malha-operacional', 'foco': 'evidence-gate'}),
        },
        {
            'id': 'cross-runtime-score',
            'title': 'Analytics Cross-Runtime',
            'type': 'metric',
            'value': unified_score,
            'unit': 'score',
            'min': 0,
            'max': 100,
            'severity': 'healthy' if unified_score >= 85 else 'attention' if unified_score >= 60 else 'degraded',
            'sources_hydrated': analytics.get('sources_hydrated', 0),
            'drilldown': '/api/runtime/analytics',
            'spa_drilldown': _spa_drilldown('/analytics', {'secao': 'malha-operacional'}),
        },
    ]


def mapear_secao_operational_mesh(signal: dict[str, Any]) -> dict[str, Any]:
    mesh = signal.get('operational_mesh') or {}
    hub = mesh.get('hub') or {}
    alert = mesh.get('alert_intelligence') or {}
    event_bus = mesh.get('event_bus') or {}
    evidence = signal.get('evidence_gate_consolidated') or {}
    analytics = signal.get('cross_runtime_analytics') or {}

    def _timeline_item(step: str, label: str, layer: dict[str, Any]) -> dict[str, Any]:
        state = layer.get('state', 'unknown')
        return {
            'step': step,
            'label': label,
            'status': estado_mesh_para_severidade(state),
            'state': state,
            'detail': layer.get('detail'),
            'available': layer.get('available', False),
            'href': '/api/runtime/operational-mesh',
            'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'malha-operacional', 'foco': step}),
        }

    return {
        'id': 'operational-mesh-chain',
        'title': 'Malha Operacional Unificada',
        'type': 'operational_mesh_chain',
        'items': {
            'chain': mesh.get('chain'),
            'timeline': [
                _timeline_item('mesh-hub', 'Runtime Mesh Hub', hub),
                _timeline_item('alert-intelligence', 'Alert Intelligence', alert),
                _timeline_item('event-bus', 'Unified Event Bus', event_bus),
                {
                    'step': 'signal-consolidator',
                    'label': 'Signal Consolidator',
                    'status': estado_mesh_para_severidade(signal.get('overall_state')),
                    'state': signal.get('overall_state'),
                    'detail': f"mesh_integrated={signal.get('mesh_integrated')}",
                    'available': bool(signal.get('hydrated')),
                    'href': '/api/runtime/operational-mesh',
                    'spa_drilldown': _spa_drilldown('/monitoramento-operacional', {'secao': 'malha-operacional'}),
                },
            ],
            'summary': {
                'mesh_integrated': signal.get('mesh_integrated'),
                'maturity_percent': signal.get('maturity_percent'),
                'overall_state': signal.get('overall_state'),
                'correlation_id': signal.get('correlation_id'),
                'artifact_path': signal.get('artifact_path'),
            },
            'evidence_gate_consolidated': evidence,
            'cross_runtime_analytics': analytics,
            'recommended_actions': signal.get('recommended_actions') or [],
        },
    }


def montar_payload_operational_mesh() -> dict[str, Any]:
    signal = carregar_operational_mesh_signal()
    analytics = carregar_cross_runtime_analytics_report()
    return {
        'schema_version': '1.0.0',
        'source': 'unified-operational-signal-consolidator',
        'hydrated': bool(signal.get('hydrated')),
        'signal': signal,
        'cross_runtime_analytics': analytics,
        'cards': mapear_cards_operational_mesh(signal),
        'section': mapear_secao_operational_mesh(signal),
    }
