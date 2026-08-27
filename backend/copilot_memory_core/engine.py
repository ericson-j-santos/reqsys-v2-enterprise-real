from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

STATUS_NAO_SOLICITADO = 'nao_solicitado'
STATUS_PENDENTE = 'pendente'
STATUS_SINCRONIZADO = 'sincronizado'
STATUS_ERRO = 'erro'
STATUS_CONFLITO = 'conflito'

CAMPOS_MEMORIA = (
    'assunto',
    'contexto',
    'estado_atual',
    'decisao',
    'pendencia',
    'proximo_passo',
    'fonte_url',
    'data_fonte',
    'validade',
)
CAMPOS_PLANNER = (
    'planner_titulo',
    'planner_status',
    'planner_percentual',
    'planner_prazo',
)
CAMPOS_CONTEUDO = ('planner_task_id',) + CAMPOS_MEMORIA + CAMPOS_PLANNER


def texto(valor: Any) -> str:
    return str(valor or '').strip()


def hash_json(valor: Mapping[str, Any]) -> str:
    bruto = json.dumps(dict(valor), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(bruto.encode('utf-8')).hexdigest()


def gerar_memory_id(planner_task_id: str) -> str:
    identificador = texto(planner_task_id)
    if not identificador:
        return ''
    digest = hashlib.sha256(identificador.encode('utf-8')).hexdigest()[:24]
    return f'planner-{digest}'


def snapshot_vazio() -> dict[str, Any]:
    return {
        'planner_task_id': None,
        'assunto': '',
        'contexto': '',
        'estado_atual': '',
        'decisao': '',
        'pendencia': '',
        'proximo_passo': '',
        'fonte_url': '',
        'data_fonte': '',
        'validade': 'ativa',
        'planner_titulo': '',
        'planner_status': '',
        'planner_percentual': 0,
        'planner_prazo': '',
    }


def montar_snapshot(
    payload: Mapping[str, Any],
    atual: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = snapshot_vazio()
    if atual:
        for campo in CAMPOS_CONTEUDO:
            if campo in atual:
                snapshot[campo] = atual[campo]

    if payload.get('planner_task_id') is not None:
        snapshot['planner_task_id'] = texto(payload['planner_task_id']) or None

    for campo in CAMPOS_MEMORIA:
        if payload.get(campo) is not None:
            snapshot[campo] = texto(payload[campo])

    for campo in CAMPOS_PLANNER:
        if payload.get(campo) is None:
            continue
        if campo == 'planner_percentual':
            percentual = int(payload[campo])
            if percentual < 0 or percentual > 100:
                raise ValueError('plannerPercentual deve estar entre 0 e 100')
            snapshot[campo] = percentual
        else:
            snapshot[campo] = texto(payload[campo])

    if not snapshot['assunto'] and snapshot['planner_titulo']:
        snapshot['assunto'] = snapshot['planner_titulo']

    return snapshot


def planner_snapshot_recebido(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if any(payload.get(campo) is None for campo in CAMPOS_PLANNER):
        return None
    return {
        'planner_titulo': texto(payload['planner_titulo']),
        'planner_status': texto(payload['planner_status']),
        'planner_percentual': int(payload['planner_percentual']),
        'planner_prazo': texto(payload['planner_prazo']),
    }


def planner_hash(snapshot: Mapping[str, Any]) -> str:
    return hash_json({campo: snapshot.get(campo, '') for campo in CAMPOS_PLANNER})


def content_hash(snapshot: Mapping[str, Any]) -> str:
    return hash_json({campo: snapshot.get(campo, '') for campo in CAMPOS_CONTEUDO})


def avaliar_planner_durante_pendencia(
    payload: Mapping[str, Any],
    planner_applied_hash: str | None,
) -> str:
    """Decide como tratar Planner recebido enquanto há alteração local pendente.

    Retorna `eco` quando o Planner ainda reflete exatamente o último estado
    confirmado; retorna `conflito` quando existe alteração remota concorrente.
    """
    recebido = planner_snapshot_recebido(payload)
    if recebido is None:
        raise ValueError(
            'origem=planner exige estado completo: título, status, percentual e prazo'
        )
    return 'eco' if hash_json(recebido) == (planner_applied_hash or '') else 'conflito'


def aplicar_decisao_planner(
    *,
    origem: str,
    solicitar_planner: bool,
    planner_task_id: str | None,
    novo_planner_hash: str,
    planner_applied_hash: str | None,
    status_atual: str | None = None,
) -> dict[str, Any]:
    """Calcula somente o estado de sincronização, sem gravar em banco ou rede."""
    origem_normalizada = texto(origem or 'reqsys').lower()

    if origem_normalizada == 'planner':
        return {
            'planner_applied_hash': novo_planner_hash,
            'atualizar_planner': False,
            'planner_sync_status': STATUS_SINCRONIZADO,
            'ultimo_erro': '',
        }

    if solicitar_planner:
        if not texto(planner_task_id):
            raise ValueError('plannerTaskId é obrigatório para atualizar o Planner')
        if novo_planner_hash != (planner_applied_hash or ''):
            return {
                'planner_applied_hash': planner_applied_hash or '',
                'atualizar_planner': True,
                'planner_sync_status': STATUS_PENDENTE,
                'ultimo_erro': '',
            }
        return {
            'planner_applied_hash': planner_applied_hash or '',
            'atualizar_planner': False,
            'planner_sync_status': STATUS_SINCRONIZADO,
            'ultimo_erro': '',
        }

    return {
        'planner_applied_hash': planner_applied_hash or '',
        'atualizar_planner': False,
        'planner_sync_status': status_atual or STATUS_NAO_SOLICITADO,
        'ultimo_erro': '',
    }
