from __future__ import annotations

import base64
import importlib.util
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


artifact = _load(
    'minimum_controlled_version_artifact',
    ROOT / 'backend' / 'app' / 'services' / 'minimum_controlled_version_artifact.py',
)
validator = _load(
    'validate_minimum_controlled_version',
    ROOT / 'scripts' / 'validate_minimum_controlled_version.py',
)


def test_emissor_reutiliza_o_mesmo_contrato_minimo_do_repositorio():
    assert artifact.REQUIRED_CONTROLS == validator.REQUIRED_CONTROLS
    manifest = artifact.build_minimum_controlled_manifest('1.2.3')
    assert validator.validate_manifest(manifest) == []


def test_manifesto_e_inserido_no_caminho_da_propria_versao():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pacote/manifest.json', '{}')

    encoded, evidence = artifact.inject_version_manifest(
        base64.b64encode(buffer.getvalue()).decode('ascii'),
        package_name='pacote',
        version='2.4.1',
    )

    assert evidence['path'] == 'governance/versions/2.4.1/minimum-controlled-version.json'
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded)), 'r') as archive:
        generated = json.loads(archive.read(f"pacote/{evidence['path']}"))
    assert generated['version'] == '2.4.1'
    assert validator.validate_manifest(generated) == []


def test_versoes_distintas_nao_compartilham_o_mesmo_caminho():
    assert artifact.manifest_relative_path('1.0.0') != artifact.manifest_relative_path('1.0.1')
