#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

REQUIRED_MANIFEST_FIELDS = {
    'profile',
    'solution_name',
    'flow_name',
    'version',
    'target_environment',
    'correlation_id',
    'sha256',
    'zip_filename',
    'files',
    'import_guardrails',
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _declared_file_paths(files: object) -> list[str]:
    if not isinstance(files, list):
        raise ValueError('Campo files do manifesto deve ser uma lista.')

    paths: list[str] = []
    for item in files:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = item.get('path')
        else:
            raise ValueError('Cada item de files deve ser string ou objeto com campo path.')

        if not isinstance(path, str) or not path.strip():
            raise ValueError('Cada item de files deve declarar um path não vazio.')
        paths.append(path)

    return sorted(paths)


def _relative_archive_file_paths(archive_files: list[str], solution_name: str) -> list[str]:
    root = solution_name.strip('/')
    if not root:
        raise ValueError('solution_name deve definir a pasta raiz do pacote.')

    prefix = f'{root}/'
    unexpected_paths = sorted(name for name in archive_files if not name.startswith(prefix))
    if unexpected_paths:
        raise ValueError(f'Arquivos fora da pasta raiz {root!r}: {unexpected_paths}')

    return sorted(name.removeprefix(prefix) for name in archive_files)


def validate(package_dir: Path) -> dict[str, object]:
    manifest_path = package_dir / 'materialization-manifest.json'
    if not manifest_path.is_file():
        raise ValueError(f'Manifesto não encontrado: {manifest_path}')

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    missing = sorted(REQUIRED_MANIFEST_FIELDS - manifest.keys())
    if missing:
        raise ValueError(f'Campos obrigatórios ausentes no manifesto: {missing}')

    if manifest['profile'] != 'teams_notification_v2':
        raise ValueError('Perfil inesperado; esperado teams_notification_v2.')
    if manifest['target_environment'] != 'dev':
        raise ValueError('Pacote pronto para importação deve ter target_environment=dev.')
    if manifest['flow_name'] != 'robo_envia_teamsv2':
        raise ValueError('Flow lógico inesperado no manifesto.')

    guardrails = manifest['import_guardrails']
    expected_guardrails = {
        'dev_only_without_approval': True,
        'flow_state_after_import': 'off_after_import',
        'requires_connection_reference': True,
        'requires_environment_variables': True,
    }
    for key, expected in expected_guardrails.items():
        if guardrails.get(key) != expected:
            raise ValueError(f'Guardrail inválido: {key}={guardrails.get(key)!r}.')

    zip_path = package_dir / manifest['zip_filename']
    if not zip_path.is_file():
        raise ValueError(f'Pacote ZIP não encontrado: {zip_path}')

    actual_sha256 = _sha256(zip_path)
    if actual_sha256 != manifest['sha256']:
        raise ValueError('SHA-256 do pacote diverge do manifesto.')

    try:
        with ZipFile(zip_path) as archive:
            archive_files = sorted(name for name in archive.namelist() if not name.endswith('/'))
            bad_file = archive.testzip()
    except BadZipFile as exc:
        raise ValueError('Pacote gerado não é um ZIP válido.') from exc

    if bad_file:
        raise ValueError(f'Arquivo corrompido dentro do ZIP: {bad_file}')

    declared_files = _declared_file_paths(manifest['files'])
    relative_archive_files = _relative_archive_file_paths(archive_files, manifest['solution_name'])
    missing_from_zip = sorted(set(declared_files) - set(relative_archive_files))
    if missing_from_zip:
        raise ValueError(f'Arquivos declarados ausentes no ZIP: {missing_from_zip}')

    readiness = {
        'status': 'ready_for_dev_import',
        'profile': manifest['profile'],
        'solution_name': manifest['solution_name'],
        'flow_name': manifest['flow_name'],
        'version': manifest['version'],
        'target_environment': manifest['target_environment'],
        'correlation_id': manifest['correlation_id'],
        'sha256': actual_sha256,
        'zip_filename': manifest['zip_filename'],
        'validated_files': len(archive_files),
        'required_manual_configuration': [
            'Microsoft Teams connection reference',
            'default Teams destination environment variable',
            'publication mode environment variable',
            'fallback enablement environment variable',
            'minimum Adaptive Card version environment variable',
            'application identifier environment variable',
        ],
        'flow_state_after_import': 'off_after_import',
    }
    return readiness


def main() -> int:
    parser = argparse.ArgumentParser(description='Valida prontidão do pacote Teams v2 para importação em DEV.')
    parser.add_argument('package_dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()

    try:
        result = validate(args.package_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    output = args.output or args.package_dir / 'dev-import-readiness.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
