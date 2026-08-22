#!/usr/bin/env python3
"""Valida corpus real/anônimo antes de qualquer benchmark OCR.

Os documentos e o manifesto real devem permanecer fora do repositório. Este
gate só aceita itens explicitamente anonimizados/homologados, aprovados e com
hash SHA-256 íntegro. Não copia nem publica conteúdo sensível.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSOES = {'.png', '.jpg', '.jpeg', '.pdf', '.tif', '.tiff'}
CLASSIFICACOES = {'ANONYMIZED_APPROVED', 'HOMOLOGATED_APPROVED'}


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


def validar_corpus(manifest_path: Path, corpus_root: Path, *, repo_root: Path = REPO_ROOT) -> dict:
    manifest_path = manifest_path.resolve()
    corpus_root = corpus_root.resolve()
    repo_root = repo_root.resolve()
    falhas: list[str] = []

    if _dentro(corpus_root, repo_root):
        falhas.append('CORPUS_ROOT_INSIDE_REPOSITORY')
    if _dentro(manifest_path, repo_root):
        falhas.append('REAL_MANIFEST_INSIDE_REPOSITORY')
    if not manifest_path.is_file():
        falhas.append('MANIFEST_NOT_FOUND')
        return {'allowed': False, 'failures': falhas, 'cases': 0}
    if not corpus_root.is_dir():
        falhas.append('CORPUS_ROOT_NOT_FOUND')
        return {'allowed': False, 'failures': falhas, 'cases': 0}

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception:
        return {'allowed': False, 'failures': falhas + ['MANIFEST_INVALID_JSON'], 'cases': 0}

    if manifest.get('schema_version') != '1.0.0':
        falhas.append('SCHEMA_VERSION_INVALID')
    approval = str(manifest.get('approval_reference') or '').strip()
    if not approval:
        falhas.append('APPROVAL_REFERENCE_REQUIRED')
    if manifest.get('contains_personal_data') is not False:
        falhas.append('MANIFEST_MUST_DECLARE_NO_PERSONAL_DATA')

    casos = manifest.get('cases')
    if not isinstance(casos, list) or not casos:
        falhas.append('CASES_REQUIRED')
        casos = []

    ids: set[str] = set()
    for indice, caso in enumerate(casos, 1):
        prefixo = f'CASE_{indice:03d}'
        case_id = str(caso.get('case_id') or '').strip()
        if not case_id:
            falhas.append(f'{prefixo}:CASE_ID_REQUIRED')
        elif case_id in ids:
            falhas.append(f'{prefixo}:CASE_ID_DUPLICATED')
        ids.add(case_id)

        if caso.get('classification') not in CLASSIFICACOES:
            falhas.append(f'{prefixo}:CLASSIFICATION_NOT_APPROVED')
        if caso.get('contains_personal_data') is not False:
            falhas.append(f'{prefixo}:PERSONAL_DATA_NOT_ALLOWED')
        if not str(caso.get('expected') or '').strip():
            falhas.append(f'{prefixo}:EXPECTED_REQUIRED_FOR_BENCHMARK')

        relativo = Path(str(caso.get('file') or ''))
        if not relativo.parts or relativo.is_absolute() or '..' in relativo.parts:
            falhas.append(f'{prefixo}:UNSAFE_FILE_PATH')
            continue
        arquivo = (corpus_root / relativo).resolve()
        if not _dentro(arquivo, corpus_root):
            falhas.append(f'{prefixo}:PATH_TRAVERSAL')
            continue
        if arquivo.suffix.lower() not in EXTENSOES:
            falhas.append(f'{prefixo}:UNSUPPORTED_EXTENSION')
        if not arquivo.is_file():
            falhas.append(f'{prefixo}:FILE_NOT_FOUND')
            continue
        esperado_hash = str(caso.get('sha256') or '').lower().strip()
        if len(esperado_hash) != 64 or any(c not in '0123456789abcdef' for c in esperado_hash):
            falhas.append(f'{prefixo}:SHA256_REQUIRED')
            continue
        if _sha256(arquivo) != esperado_hash:
            falhas.append(f'{prefixo}:SHA256_MISMATCH')

    return {
        'allowed': not falhas,
        'failures': falhas,
        'cases': len(casos),
        'approval_reference_present': bool(approval),
        'corpus_in_repository': _dentro(corpus_root, repo_root),
        'content_exposed': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--corpus-root', type=Path, required=True)
    args = parser.parse_args()
    resultado = validar_corpus(args.manifest, args.corpus_root)
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return 0 if resultado['allowed'] else 4


if __name__ == '__main__':
    raise SystemExit(main())
