#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.requisito_ml_p3 import (  # noqa: E402
    EventoClassificacaoML,
    amostras_aprovadas_para_treino,
    avaliar_holdout,
    calcular_drift,
    carregar_amostras_observadas,
    carregar_holdout,
    carregar_politica_runtime,
    treinar_modelo_runtime,
    validar_holdout_imutavel,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Avalia prontidão P3 do classificador de requisitos.')
    parser.add_argument(
        '--dataset-p2',
        type=Path,
        default=BACKEND / 'data/ml/requisitos_classificador_v1.jsonl',
    )
    parser.add_argument(
        '--holdout',
        type=Path,
        default=BACKEND / 'data/ml/requisitos_holdout_p3_v1.jsonl',
    )
    parser.add_argument(
        '--observados',
        type=Path,
        default=BACKEND / 'data/ml/requisitos_observados_p3_v1.jsonl',
    )
    parser.add_argument(
        '--politica',
        type=Path,
        default=BACKEND / 'data/ml/politica_runtime_requisitos_p3_v1.json',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'artifacts/ml-requirement-classifier-p3/report.json',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    politica = carregar_politica_runtime(args.politica)
    holdout, holdout_sha = carregar_holdout(args.holdout)
    validar_holdout_imutavel(args.holdout, politica)
    observados = carregar_amostras_observadas(args.observados)
    aprovadas = amostras_aprovadas_para_treino(observados)

    modelo = treinar_modelo_runtime(args.dataset_p2)
    resultado_holdout = avaliar_holdout(
        modelo,
        holdout,
        holdout_sha256=holdout_sha,
        politica=politica,
    )

    eventos = []
    for item in holdout:
        predicao = modelo.classificar(item.texto)
        eventos.append(
            EventoClassificacaoML(
                categoria=predicao.categoria,
                confianca=predicao.confianca,
                engine=predicao.modelo,
            )
        )
    drift_smoke = calcular_drift(eventos, politica=politica)

    revisoes = Counter(item.revisao_status for item in observados)
    quantidade_aprovadas = len(aprovadas)
    if resultado_holdout.status != 'APROVADO':
        readiness = 'BLOQUEADO_QUALIDADE'
    elif quantidade_aprovadas >= politica.minimo_amostras_reais_aprovadas_active and not drift_smoke.alertas:
        readiness = 'APROVADO_PARA_ACTIVE'
    elif quantidade_aprovadas >= politica.minimo_amostras_reais_aprovadas_canary and not drift_smoke.alertas:
        readiness = 'APROVADO_PARA_CANARY'
    else:
        readiness = 'APROVADO_PARA_SHADOW'

    report = {
        'schema_version': '1.0.0',
        'readiness': readiness,
        'politica_versao': politica.versao,
        'modelo_versao': politica.modelo_versao,
        'holdout': resultado_holdout.como_dict(),
        'observados': {
            'total': len(observados),
            'status': dict(revisoes),
            'aprovados_para_treino': quantidade_aprovadas,
            'minimo_canary': politica.minimo_amostras_reais_aprovadas_canary,
            'minimo_active': politica.minimo_amostras_reais_aprovadas_active,
            'nota': 'Amostras PENDENTE_HUMANA nunca entram no treino nem liberam canary.',
        },
        'drift_smoke_holdout': drift_smoke.como_dict(),
        'runtime': {
            'modo_padrao': politica.modo_padrao,
            'canary_percentual': politica.canary_percentual,
            'confianca_minima_modelo': politica.confianca_minima_modelo,
            'production_touched': False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f"readiness={readiness}")
    print(f"holdout_sha256={holdout_sha}")
    print(f"baseline_macro_f1={resultado_holdout.baseline_macro_f1:.4f}")
    print(f"modelo_macro_f1={resultado_holdout.modelo_macro_f1:.4f}")
    print(f"ganho_macro_f1={resultado_holdout.ganho_macro_f1:.4f}")
    print(f"observados_total={len(observados)}")
    print(f"observados_aprovados={quantidade_aprovadas}")
    print(f"drift_js={drift_smoke.js_divergence:.4f}")
    print(f"evidencia={args.output}")

    return 0 if resultado_holdout.status == 'APROVADO' else 2


if __name__ == '__main__':
    raise SystemExit(main())
