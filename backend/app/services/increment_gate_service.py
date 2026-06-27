from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import settings

_VALID_INCREMENT_TYPES = frozenset({'new_front', 'gap_fix', 'close_duplicate', 'hotfix', 'consolidate'})


def _relatorio_permissivo() -> dict[str, Any]:
    return {
        'increment_gate': {
            'allowed_increment_types': sorted(_VALID_INCREMENT_TYPES),
            'new_front_allowed': True,
            'blockers': [],
        },
        'automatic_backlog': [],
        'duplicate_pr_groups': [],
    }


def carregar_relatorio_coordenador() -> dict[str, Any] | None:
    candidatos: list[Path] = []
    env_path = (os.environ.get('COORDENADOR_STATUS_JSON') or '').strip()
    if env_path:
        candidatos.append(Path(env_path))
    candidatos.append(Path('artifacts/coordenador-status/coordenador-status.json'))
    candidatos.append(Path(__file__).resolve().parents[3] / 'artifacts/coordenador-status/coordenador-status.json')

    for caminho in candidatos:
        if caminho.is_file():
            return json.loads(caminho.read_text(encoding='utf-8'))
    return None


def verificar_increment_gate(
    increment_type: str = 'new_front',
    reference: str = '',
    *,
    strict: bool | None = None,
) -> dict[str, Any]:
    if increment_type not in _VALID_INCREMENT_TYPES:
        return {
            'permitido': False,
            'motivo': 'increment_type_invalido',
            'detalhe': f"Tipo '{increment_type}' nao suportado.",
        }

    if strict is None:
        strict = settings.normalized_environment in {'producao', 'homologacao'}

    relatorio = carregar_relatorio_coordenador()
    if relatorio is None:
        if strict:
            return {
                'permitido': False,
                'motivo': 'coordenador_status_ausente',
                'detalhe': 'Relatorio coordenador-status.json ausente em ambiente governado.',
            }
        relatorio = _relatorio_permissivo()
        return {
            'permitido': True,
            'motivo': 'gate_relaxado_sem_relatorio',
            'detalhe': 'Increment gate relaxado fora de producao/homologacao sem relatorio local.',
        }

    gate = relatorio.get('increment_gate') or {}
    allowed_types = set(gate.get('allowed_increment_types') or [])
    if increment_type not in allowed_types:
        blockers = ', '.join(gate.get('blockers') or []) or 'condicao operacional'
        return {
            'permitido': False,
            'motivo': 'increment_type_nao_permitido',
            'detalhe': f'Bloqueios ativos: {blockers}. Tipos permitidos: {", ".join(sorted(allowed_types)) or "nenhum"}.',
        }

    if increment_type == 'new_front' and not gate.get('new_front_allowed'):
        return {
            'permitido': False,
            'motivo': 'nova_frente_bloqueada',
            'detalhe': 'Coordenador bloqueou novas frentes. Resolva bloqueios ou use gap_fix/hotfix.',
        }

    if increment_type == 'gap_fix' and reference:
        backlog_ids = {
            str(item.get('id'))
            for item in relatorio.get('automatic_backlog') or []
            if item.get('id')
        }
        if reference not in backlog_ids:
            return {
                'permitido': False,
                'motivo': 'gap_fix_invalido',
                'detalhe': f'Referencia {reference} nao encontrada no backlog atual.',
            }

    return {
        'permitido': True,
        'motivo': 'incremento_permitido',
        'detalhe': 'Increment gate aprovado para a operacao solicitada.',
    }
