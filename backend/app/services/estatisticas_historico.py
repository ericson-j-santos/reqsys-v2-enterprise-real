from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HISTORY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'estatisticas-history' / 'snapshots.json'
MAX_SNAPSHOTS = 60


def _agora_iso() -> str:
    return datetime.now(UTC).isoformat()


def carregar_historico() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return list(payload.get('snapshots') or [])


def registrar_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    historico = carregar_historico()
    resumo = {
        'schema_version': snapshot.get('schema_version', '2.0.0'),
        'coletado_em': snapshot.get('coletado_em') or _agora_iso(),
        'correlation_id': snapshot.get('correlation_id'),
        'ambiente': snapshot.get('ambiente'),
        'resumo': snapshot.get('resumo') or {},
        'indicadores_resumo': [
            {
                'id': item.get('id'),
                'valorAtual': item.get('valorAtual'),
                'estadoAtual': item.get('estadoAtual'),
                'tendencia': item.get('tendencia'),
            }
            for item in snapshot.get('indicadores') or []
        ],
    }
    historico.append(resumo)
    historico = historico[-MAX_SNAPSHOTS:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(historico, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return historico


def calcular_tendencias(historico: list[dict[str, Any]]) -> dict[str, str]:
    if len(historico) < 2:
        return {}
    anterior = historico[-2].get('indicadores_resumo') or []
    atual = historico[-1].get('indicadores_resumo') or []
    mapa_anterior = {item['id']: item.get('valorAtual') for item in anterior if item.get('id')}
    tendencias: dict[str, str] = {}
    for item in atual:
        indicador_id = item.get('id')
        if not indicador_id or indicador_id not in mapa_anterior:
            continue
        try:
            prev_val = float(mapa_anterior[indicador_id])
            curr_val = float(item.get('valorAtual') or 0)
        except (TypeError, ValueError):
            continue
        if curr_val > prev_val:
            tendencias[indicador_id] = 'subindo'
        elif curr_val < prev_val:
            tendencias[indicador_id] = 'caindo'
        else:
            tendencias[indicador_id] = 'estavel'
    return tendencias
