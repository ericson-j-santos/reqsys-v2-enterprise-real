"""Núcleo portátil do Copilot Memory.

Sem dependência de FastAPI, SQLAlchemy, ReqSys, Planner ou Power Automate.
"""

from .engine import (
    CAMPOS_CONTEUDO,
    CAMPOS_MEMORIA,
    CAMPOS_PLANNER,
    STATUS_CONFLITO,
    STATUS_ERRO,
    STATUS_NAO_SOLICITADO,
    STATUS_PENDENTE,
    STATUS_SINCRONIZADO,
    aplicar_decisao_planner,
    avaliar_planner_durante_pendencia,
    content_hash,
    gerar_memory_id,
    hash_json,
    montar_snapshot,
    planner_hash,
    planner_snapshot_recebido,
    snapshot_vazio,
    texto,
)

__all__ = [
    'CAMPOS_CONTEUDO',
    'CAMPOS_MEMORIA',
    'CAMPOS_PLANNER',
    'STATUS_CONFLITO',
    'STATUS_ERRO',
    'STATUS_NAO_SOLICITADO',
    'STATUS_PENDENTE',
    'STATUS_SINCRONIZADO',
    'aplicar_decisao_planner',
    'avaliar_planner_durante_pendencia',
    'content_hash',
    'gerar_memory_id',
    'hash_json',
    'montar_snapshot',
    'planner_hash',
    'planner_snapshot_recebido',
    'snapshot_vazio',
    'texto',
]

__version__ = '1.0.0'
