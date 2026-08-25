#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.requisito_ml import (  # noqa: E402
    avaliar_promocao_ml,
    carregar_dataset_ml,
    carregar_politica_ml,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Treina, valida e aplica o gate governado do classificador supervisionado de requisitos.'
    )
    parser.add_argument(
        '--dataset',
        type=Path,
        default=BACKEND_ROOT / 'data/ml/requisitos_classificador_v1.jsonl',
    )
    parser.add_argument(
        '--politica',
        type=Path,
        default=BACKEND_ROOT / 'data/ml/politica_promocao_requisitos_v1.json',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=REPO_ROOT / 'artifacts/ml-requirement-classifier/metrics.json',
    )
    parser.add_argument(
        '--model-output',
        type=Path,
        default=REPO_ROOT / 'artifacts/ml-requirement-classifier/model.json',
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        registros, dataset_sha256 = carregar_dataset_ml(args.dataset)
        politica = carregar_politica_ml(args.politica)
        resultado, modelo = avaliar_promocao_ml(
            registros,
            dataset_sha256=dataset_sha256,
            politica=politica,
        )
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f'[ERRO] gate ML fail-closed: {exc}', file=sys.stderr)
        return 3

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    args.model_output.write_text(
        json.dumps(modelo.exportar_estado(), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )

    print(f'status={resultado.status}')
    print(f'dataset_sha256={resultado.dataset_sha256}')
    print(f'treino={resultado.quantidade_treino}')
    print(f'validacao={resultado.quantidade_validacao}')
    print(f'baseline_macro_f1={resultado.baseline.macro_f1:.4f}')
    print(f'modelo_macro_f1={resultado.modelo.macro_f1:.4f}')
    print(f'ganho_macro_f1={resultado.ganho_macro_f1:.4f}')
    print(f'evidencia={args.output}')

    return 0 if resultado.status == 'APROVADO' else 2


if __name__ == '__main__':
    raise SystemExit(main())
