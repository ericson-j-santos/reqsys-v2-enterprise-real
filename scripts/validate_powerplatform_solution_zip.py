#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

REQUIRED_ROOT_FILES = {'solution.xml', 'customizations.xml'}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate(solution_zip: Path, *, expected_solution: str) -> dict[str, object]:
    if not solution_zip.is_file():
        raise ValueError(f'Pacote não encontrado: {solution_zip}')
    if solution_zip.suffix.lower() != '.zip':
        raise ValueError('O pacote oficial deve ser um arquivo ZIP.')

    try:
        with ZipFile(solution_zip) as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith('/'))
            corrupted = archive.testzip()
            solution_xml = archive.read('solution.xml').decode('utf-8-sig', errors='strict')
    except KeyError as exc:
        raise ValueError(f'Arquivo obrigatório ausente no pacote: {exc.args[0]}') from exc
    except (BadZipFile, UnicodeDecodeError) as exc:
        raise ValueError('Pacote oficial inválido ou corrompido.') from exc

    if corrupted:
        raise ValueError(f'Arquivo corrompido dentro do pacote: {corrupted}')

    root_files = {name for name in names if '/' not in name}
    missing = sorted(REQUIRED_ROOT_FILES - root_files)
    if missing:
        raise ValueError(f'Arquivos obrigatórios ausentes na raiz: {missing}')

    if expected_solution not in solution_xml:
        raise ValueError(f'solution.xml não referencia a solution esperada: {expected_solution}')

    flow_files = [name for name in names if '/Workflows/' in f'/{name}' or name.startswith('Workflows/')]
    if not flow_files:
        raise ValueError('Pacote não contém componente de workflow/cloud flow exportado pelo Power Platform.')

    return {
        'status': 'official_solution_valid',
        'solution_name': expected_solution,
        'zip_filename': solution_zip.name,
        'sha256': sha256(solution_zip),
        'files': len(names),
        'workflow_components': len(flow_files),
        'required_root_files': sorted(REQUIRED_ROOT_FILES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Valida um ZIP oficial exportado pelo Power Platform.')
    parser.add_argument('solution_zip', type=Path)
    parser.add_argument('--expected-solution', default='ReqSysTeamsNotifications')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()

    try:
        result = validate(args.solution_zip, expected_solution=args.expected_solution)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
