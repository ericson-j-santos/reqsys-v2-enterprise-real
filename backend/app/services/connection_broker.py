from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parents[2] / 'config' / 'connectors' / 'connection-broker-registry.json'

_STATUS_BLOQUEADOS = frozenset({'blocked', 'unavailable', 'misconfigured'})
_STATUS_PENDENTES = frozenset({'missing_permission', 'insufficient_permission', 'expired'})


def _carregar_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {'version': '1.0.0', 'capabilities': []}
    with REGISTRY_PATH.open(encoding='utf-8') as handle:
        return json.load(handle)


def listar_conectores() -> list[dict[str, Any]]:
    registry = _carregar_registry()
    conectores: list[dict[str, Any]] = []
    for item in registry.get('capabilities', []):
        if not isinstance(item, dict):
            continue
        conectores.append(
            {
                'ambiente': item.get('ambiente', ''),
                'conector': item.get('conector', ''),
                'capability': item.get('capability', ''),
                'status': item.get('status', 'unavailable'),
                'criticidade': item.get('criticidade', 'medium'),
                'acao_sugerida': item.get('acao_sugerida', ''),
                'requires_human_confirmation': bool(item.get('requires_human_confirmation', False)),
            }
        )
    return conectores


def resumo_conectores(conectores: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    items = conectores if conectores is not None else listar_conectores()
    prontos = sum(1 for item in items if item.get('status') == 'ready')
    pendentes = sum(1 for item in items if item.get('status') in _STATUS_PENDENTES)
    bloqueados = sum(1 for item in items if item.get('status') in _STATUS_BLOQUEADOS)
    if bloqueados:
        estado_geral = 'bloqueado'
    elif pendentes:
        estado_geral = 'amarelo'
    elif prontos:
        estado_geral = 'verde'
    else:
        estado_geral = 'desconhecido'
    return {
        'total': len(items),
        'prontos': prontos,
        'pendentes': pendentes,
        'bloqueados': bloqueados,
        'estado_geral': estado_geral,
    }


def montar_health_payload(correlation_id: str) -> dict[str, Any]:
    conectores = listar_conectores()
    resumo = resumo_conectores(conectores)
    return {
        'correlation_id': correlation_id,
        'conectores': conectores,
        'resumo': resumo,
        'registry_path': str(REGISTRY_PATH.name),
        'registry_version': _carregar_registry().get('version', '1.0.0'),
    }
