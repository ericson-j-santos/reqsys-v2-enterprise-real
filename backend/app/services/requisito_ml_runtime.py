from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.requisito_ml import ClassificadorRequisitoSupervisionado
from app.services.requisito_ml_p3 import (
    DecisaoRuntimeML,
    PoliticaRuntimeML,
    carregar_amostras_observadas,
    carregar_politica_runtime,
    classificar_runtime,
    treinar_modelo_runtime,
    validar_holdout_imutavel,
)

logger = logging.getLogger('reqsys.requisito_ml_runtime')

_BACKEND = Path(__file__).resolve().parents[2]
_DATASET_P2 = _BACKEND / 'data/ml/requisitos_classificador_v1.jsonl'
_HOLDOUT = _BACKEND / 'data/ml/requisitos_holdout_p3_v1.jsonl'
_OBSERVADOS = _BACKEND / 'data/ml/requisitos_observados_p3_v1.jsonl'
_POLITICA = _BACKEND / 'data/ml/politica_runtime_requisitos_p3_v1.json'
_MODO_ENV = 'REQSYS_ML_REQUISITOS_MODO'
_MODOS_OBSERVACIONAIS = {'off', 'shadow'}


@dataclass(frozen=True)
class ContextoRuntimeRequisitoML:
    politica: PoliticaRuntimeML
    modelo: ClassificadorRequisitoSupervisionado
    amostras_aprovadas: int


@lru_cache(maxsize=1)
def _carregar_contexto() -> ContextoRuntimeRequisitoML:
    politica = carregar_politica_runtime(_POLITICA)
    validar_holdout_imutavel(_HOLDOUT, politica)
    observados = carregar_amostras_observadas(_OBSERVADOS)
    modelo = treinar_modelo_runtime(_DATASET_P2)
    return ContextoRuntimeRequisitoML(
        politica=politica,
        modelo=modelo,
        amostras_aprovadas=sum(
            1 for item in observados if item.revisao_status == 'APROVADO'
        ),
    )


def limpar_cache_runtime() -> None:
    _carregar_contexto.cache_clear()


def modo_runtime_configurado() -> str:
    return (os.getenv(_MODO_ENV) or 'off').strip().lower() or 'off'


def avaliar_requisito_observacional(
    texto: str,
    *,
    correlation_id: str,
) -> DecisaoRuntimeML | None:
    modo = modo_runtime_configurado()
    if modo == 'off':
        return None
    if modo not in _MODOS_OBSERVACIONAIS:
        logger.error(
            'requisito_ml_runtime_modo_bloqueado modo=%s correlation_id=%s',
            modo,
            correlation_id,
        )
        return None

    try:
        contexto = _carregar_contexto()
        decisao = classificar_runtime(
            texto,
            correlation_id=correlation_id,
            politica=contexto.politica,
            modelo=contexto.modelo,
            modo='shadow',
            amostras_reais_aprovadas=contexto.amostras_aprovadas,
        )
    except Exception as exc:
        logger.error(
            'requisito_ml_runtime_indisponivel erro=%s correlation_id=%s',
            type(exc).__name__,
            correlation_id,
        )
        return None

    logger.info(
        'requisito_ml_shadow_avaliado correlation_id=%s modo=%s engine_resposta=%s baseline_categoria=%s modelo_categoria=%s modelo_confianca=%s fallback_reason=%s amostras_aprovadas=%s',
        correlation_id,
        decisao.modo,
        decisao.engine,
        decisao.baseline_categoria,
        decisao.modelo_categoria,
        decisao.modelo_confianca,
        decisao.fallback_reason,
        contexto.amostras_aprovadas,
    )
    return decisao
