from __future__ import annotations

import base64
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

from app.schemas.copilot_memory import CopilotMemoryLowCodePackageRequest
from app.services.copilot_memory_lowcode_factory import FACTORY_PROFILE_VERSION, PACKAGE_NAME
from app.services.copilot_memory_simple_factory import gerar_copilot_memory_simple_solution
from app.services.minimum_controlled_version_artifact import (
    build_minimum_controlled_manifest,
    inject_version_manifest,
    manifest_relative_path,
)

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[2] / 'scripts' / 'validate_minimum_controlled_version.py'
)
spec = importlib.util.spec_from_file_location('validate_minimum_controlled_version', VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


def _manifesto_gerado(profile: str) -> tuple[dict, dict, str]:
    solution = gerar_copilot_memory_simple_solution(
        CopilotMemoryLowCodePackageRequest(profile=profile)
    )
    evidence = solution['package']['minimum_controlled_version_manifest']
    archive_path = f"{PACKAGE_NAME}/{evidence['path']}"
    raw = base64.b64decode(solution['package']['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        manifest = json.loads(archive.read(archive_path))
    return solution, manifest, archive_path


@pytest.mark.parametrize(
    'profile',
    [
        'copilot_memory_corporativo_restrito',
        'copilot_memory_corporativo_com_api',
        'copilot_memory_minimal',
        'copilot_memory_enterprise',
    ],
)
def test_todo_perfil_emitido_pela_api_recebe_manifesto_da_propria_versao(profile):
    solution, manifest, archive_path = _manifesto_gerado(profile)

    assert archive_path == (
        f'{PACKAGE_NAME}/governance/versions/{FACTORY_PROFILE_VERSION}/'
        'minimum-controlled-version.json'
    )
    assert manifest['version'] == FACTORY_PROFILE_VERSION
    assert manifest['maturity'] == 'MINIMUM_CONTROLLED'
    assert manifest['release_allowed'] is True
    assert validator.validate_manifest(manifest) == []
    assert solution['governance']['minimum_controlled_version_manifest']['path'] == (
        manifest_relative_path(FACTORY_PROFILE_VERSION)
    )


def test_pacote_simples_inclui_manifesto_no_checksum_de_integridade():
    solution, _, _ = _manifesto_gerado('copilot_memory_corporativo_restrito')
    evidence = solution['package']['minimum_controlled_version_manifest']
    raw = base64.b64decode(solution['package']['zip_base64'])

    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        checksums = archive.read(f'{PACKAGE_NAME}/checksums.sha256').decode('utf-8')

    assert f"{evidence['sha256']}  {evidence['path']}" in checksums


def test_cada_semver_possui_caminho_proprio_e_nao_sobrescreve_outra_versao():
    assert manifest_relative_path('1.2.3') != manifest_relative_path('1.2.4')
    assert build_minimum_controlled_manifest('1.2.3')['version'] == '1.2.3'
    assert build_minimum_controlled_manifest('1.2.4')['version'] == '1.2.4'


def test_injecao_falha_fechado_para_versao_ou_pacote_invalido():
    empty_zip = io.BytesIO()
    with zipfile.ZipFile(empty_zip, 'w'):
        pass
    zip_base64 = base64.b64encode(empty_zip.getvalue()).decode('ascii')

    with pytest.raises(ValueError, match='Versionamento Semântico'):
        inject_version_manifest(zip_base64, package_name='pacote', version='v1')

    with pytest.raises(ValueError, match='package_name'):
        inject_version_manifest(zip_base64, package_name='../pacote', version='1.0.0')


def test_mesma_versao_nao_pode_ser_injetada_duas_vezes_no_mesmo_zip():
    empty_zip = io.BytesIO()
    with zipfile.ZipFile(empty_zip, 'w'):
        pass
    zip_base64 = base64.b64encode(empty_zip.getvalue()).decode('ascii')

    first, _ = inject_version_manifest(
        zip_base64,
        package_name='pacote',
        version='1.0.0',
    )
    with pytest.raises(ValueError, match='já existe'):
        inject_version_manifest(first, package_name='pacote', version='1.0.0')
