#!/usr/bin/env python3
"""Prepara um manifesto *rascunho* para certificação OCR com corpus externo.

Este utilitário reduz o trabalho manual sem fabricar evidência: ele apenas
inventaria arquivos suportados e calcula SHA-256. Aprovação, classificação,
verdade conhecida e referência de revisão humana permanecem vazias/pendentes,
de modo que o gate oficial continue fail-closed até revisão humana real.

Nenhum conteúdo do documento é copiado, extraído ou publicado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSOES = {'.png', '.jpg', '.jpeg', '.pdf', '.tif', '.tiff'}


def _dentro(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            digest.update(bloco)
    return digest.hexdigest()


def _case_id(relativo: Path, usado: set[str]) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', relativo.with_suffix('').as_posix().lower()).strip('-')
    base = base or 'documento'
    candidato = base
    indice = 2
    while candidato in usado:
        candidato = f'{base}-{indice}'
        indice += 1
    usado.add(candidato)
    return candidato


def preparar_manifesto(corpus_root: Path, output: Path, *, repo_root: Path = REPO_ROOT) -> dict:
    corpus_root = corpus_root.resolve()
    output = output.resolve()
    repo_root = repo_root.resolve()

    if not corpus_root.is_dir():
        raise ValueError('CORPUS_ROOT_NOT_FOUND')
    if _dentro(corpus_root, repo_root):
        raise ValueError('CORPUS_ROOT_INSIDE_REPOSITORY')
    if _dentro(output, repo_root):
        raise ValueError('MANIFEST_OUTPUT_INSIDE_REPOSITORY')

    arquivos = sorted(
        p for p in corpus_root.rglob('*')
        if p.is_file() and p.suffix.lower() in EXTENSOES
    )
    if not arquivos:
        raise ValueError('NO_SUPPORTED_DOCUMENTS')

    usados: set[str] = set()
    casos: list[dict] = []
    for arquivo in arquivos:
        relativo = arquivo.relative_to(corpus_root)
        partes = relativo.parts
        tipo = partes[0].upper() if len(partes) > 1 else 'UNKNOWN'
        casos.append({
            'case_id': _case_id(relativo, usados),
            'document_type': tipo,
            'file': relativo.as_posix(),
            'sha256': _sha256(arquivo),
            # Intencionalmente inválido até revisão humana real.
            'classification': 'PENDING_HUMAN_REVIEW',
            'contains_personal_data': None,
            'expected': '',
            'human_review_reference': '',
            'max_cer': 0.10,
        })

    manifesto = {
        'schema_version': '1.0.0',
        'approval_reference': '',
        # Não presumir anonimização sem confirmação humana.
        'contains_personal_data': None,
        'max_average_cer': 0.10,
        'min_exact_match': 0.80,
        'cases': casos,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'status': 'DRAFT_REQUIRES_HUMAN_REVIEW',
        'cases': len(casos),
        'output': str(output),
        'content_exposed': False,
        'ready_for_certification': False,
        'required_human_fields': [
            'approval_reference',
            'contains_personal_data=false',
            'classification',
            'expected',
            'human_review_reference',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        resultado = preparar_manifesto(args.corpus_root, args.output)
    except ValueError as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, ensure_ascii=False, sort_keys=True))
        return 4
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
