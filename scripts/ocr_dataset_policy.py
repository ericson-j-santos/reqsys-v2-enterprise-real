#!/usr/bin/env python3
"""Gate fail-closed de licença para datasets OCR opcionais."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'benchmark' / 'ocr' / 'datasets-v1.json'


def carregar_manifesto(path: Path = MANIFEST) -> dict:
    dados = json.loads(path.read_text(encoding='utf-8'))
    if not dados.get('datasets'):
        raise ValueError('manifesto de datasets vazio')
    return dados


def avaliar_dataset(dataset_id: str, *, contexto: str, aceite_humano: bool, path: Path = MANIFEST) -> dict:
    manifesto = carregar_manifesto(path)
    item = next((x for x in manifesto['datasets'] if x.get('id') == dataset_id), None)
    if item is None:
        return {'allowed': False, 'reason': 'DATASET_UNKNOWN', 'dataset_id': dataset_id, 'context': contexto}
    permitidos = set(item.get('allowed_contexts') or [])
    if contexto not in permitidos:
        return {
            'allowed': False,
            'reason': 'CONTEXT_NOT_LICENSED',
            'dataset_id': dataset_id,
            'context': contexto,
            'license_status': item.get('license_status'),
        }
    if item.get('requires_human_acceptance') and not aceite_humano:
        return {
            'allowed': False,
            'reason': 'HUMAN_LICENSE_ACCEPTANCE_REQUIRED',
            'dataset_id': dataset_id,
            'context': contexto,
            'license_status': item.get('license_status'),
        }
    return {
        'allowed': True,
        'reason': 'POLICY_OK',
        'dataset_id': dataset_id,
        'context': contexto,
        'license_status': item.get('license_status'),
        'source': item.get('source'),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset_id')
    parser.add_argument('--context', default='corporate-ci', choices=['corporate-ci', 'research-noncommercial'])
    parser.add_argument('--accepted', action='store_true', help='Confirma que o responsável autorizado aceitou os termos aplicáveis.')
    args = parser.parse_args()
    resultado = avaliar_dataset(args.dataset_id, contexto=args.context, aceite_humano=args.accepted)
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return 0 if resultado['allowed'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
