from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import app.services.vba_governed_evaluation as governed
from app.services.vba_governed_evaluation import (
    VbaGovernedEvaluationError,
    evaluate_vba_governed,
)


def _source(*, option_explicit: bool = False) -> str:
    option = 'Option Explicit\n' if option_explicit else ''
    return (
        'Attribute VB_Name = "modAvaliacaoReqSys"\n'
        f'{option}'
        'Public Sub Avaliar(ByVal valor As Long)\n'
        '    If valor > 10 Then Range("A1").Value = "ALTO"\n'
        'End Sub\n'
    )


def _evaluate(source: str | None = None) -> dict:
    return evaluate_vba_governed(
        source or _source(),
        file_name='modAvaliacaoReqSys.bas',
        version='0.1.0',
    )


def _package(result: dict) -> bytes:
    return base64.b64decode(result['package']['base64'], validate=True)


def _independent_readback(package: bytes) -> dict[str, bytes]:
    assert zipfile.is_zipfile(BytesIO(package))
    with zipfile.ZipFile(BytesIO(package), 'r') as archive:
        assert archive.testzip() is None
        infos = archive.infolist()
        names = [info.filename for info in infos]
        assert names == sorted(names)
        assert len(names) == len(set(names))
        assert all(not name.startswith('/') and '..' not in name.split('/') for name in names)
        assert all('\\' not in name for name in names)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos)
        assert all(info.compress_type == zipfile.ZIP_STORED for info in infos)
        files = {name: archive.read(name) for name in names}

    declared = {}
    for line in files['checksums.sha256'].decode('utf-8').splitlines():
        digest, path = line.split('  ', 1)
        declared[path] = digest
    assert set(declared) == set(files) - {'checksums.sha256'}
    for path, digest in declared.items():
        assert hashlib.sha256(files[path]).hexdigest() == digest
    return files


def _validate_vmc(manifest: dict) -> list[str]:
    module_path = (
        Path(__file__).resolve().parents[2]
        / 'scripts'
        / 'validate_minimum_controlled_version.py'
    )
    spec = importlib.util.spec_from_file_location('validate_minimum_controlled_version', module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_manifest(manifest)


def test_pipeline_emite_pacote_deterministico_e_nao_liberavel():
    first = _evaluate()
    second = _evaluate()

    assert first['status'] == 'AWAITING_DYNAMIC_VALIDATION'
    assert first['candidate_status'] == 'PROPOSED_NOT_RELEASED'
    assert first['preservation']['status'] == 'PASS'
    assert first['functional_equivalence'] == 'NOT_PROVEN'
    assert first['dynamic_validation'] == 'FUTURE_REQUIRED'
    assert first['release_allowed'] is False
    assert first['execution_performed'] is False
    assert first['office_execution'] is False
    assert first['source_persisted'] is False
    assert first['package'] == second['package']

    package = _package(first)
    assert hashlib.sha256(package).hexdigest() == first['package']['sha256']
    assert len(package) == first['package']['size']
    files = _independent_readback(package)

    candidate_path = 'source/candidate/modAvaliacaoReqSys.bas'
    candidate = files[candidate_path].decode('utf-8')
    assert candidate.count('Option Explicit') == 1
    assert candidate.index('Option Explicit') < candidate.index('Public Sub')
    original_path = 'source/original-normalized/modAvaliacaoReqSys.bas'
    assert files[original_path].decode('utf-8') == _source()

    manifest = json.loads(files['manifest.json'])
    assert manifest['static_preservation'] == 'PASS'
    assert manifest['functional_equivalence'] == 'NOT_PROVEN'
    assert manifest['release_allowed'] is False
    assert manifest['execution_performed'] is False
    assert manifest['source_included_in_returned_package'] is True
    assert manifest['server_persistence_performed'] is False

    vmc_path = 'governance/versions/0.1.0/minimum-controlled-version.json'
    vmc = json.loads(files[vmc_path])
    assert vmc['maturity'] == 'EXPERIMENTAL'
    assert vmc['release_allowed'] is False
    assert vmc['controls']['secret_scanning'] == 'PASS'
    assert vmc['controls']['error_handling'] == 'FAIL'
    assert vmc['controls']['automated_tests'] == 'FAIL'
    assert vmc['contextual_controls']['functional_equivalence'] == 'FAIL'
    assert _validate_vmc(vmc) == []


def test_option_explicit_existente_permanece_unico_e_idempotente():
    result = _evaluate(_source(option_explicit=True))
    files = _independent_readback(_package(result))
    candidate = files['source/candidate/modAvaliacaoReqSys.bas'].decode('utf-8')

    assert result['transformation']['status'] == 'ALREADY_APPLIED'
    assert candidate == _source(option_explicit=True)
    assert candidate.count('Option Explicit') == 1


def test_segredo_bloqueia_pacote_sem_expor_valor():
    secret = 'nao-pode-vazar-123'
    source = f'Public Const API_KEY = "{secret}"\nPublic Sub X()\nEnd Sub\n'

    with pytest.raises(VbaGovernedEvaluationError) as exc_info:
        _evaluate(source)

    error = exc_info.value
    assert error.code == 'VBA_GOVERNED_SECRET_LITERAL_BLOCKED'
    assert error.context['package_emitted'] is False
    assert error.context['findings'] == [{'kind': 'credential_literal', 'line': 1}]
    assert secret not in str(error.context)
    assert secret not in str(error)


@pytest.mark.parametrize(
    ('declaration', 'kind'),
    [
        ('Public Const CLIENT_SECRET = "client-secret-value"', 'credential_literal'),
        ('Public Const token = "token-value-123"', 'credential_literal'),
        (
            'Public Const API_KEY As String = "typed-key-value"',
            'credential_literal',
        ),
        ('Public Const TOKEN$ = "typed-token-value"', 'credential_literal'),
        (
            "' -----BEGIN RSA PRIVATE KEY----- material",
            'private_key_material',
        ),
        (
            'Public Const URL = "https://user:password@example.invalid/path"',
            'url_embedded_credential',
        ),
    ],
)
def test_outros_literais_sensiveis_sao_bloqueados(declaration, kind):
    with pytest.raises(VbaGovernedEvaluationError) as exc_info:
        _evaluate(f'{declaration}\nPublic Sub X()\nEnd Sub\n')

    assert exc_info.value.code == 'VBA_GOVERNED_SECRET_LITERAL_BLOCKED'
    assert exc_info.value.context['findings'][0]['kind'] == kind


def test_teste_do_teste_bloqueia_drift_estatico(monkeypatch):
    original_transform = governed._ensure_option_explicit

    def drifting_transform(source: str):
        candidate, evidence = original_transform(source)
        return candidate.replace('valor > 10', 'valor < 10'), evidence

    monkeypatch.setattr(governed, '_ensure_option_explicit', drifting_transform)

    with pytest.raises(VbaGovernedEvaluationError) as exc_info:
        _evaluate()

    assert exc_info.value.code == 'VBA_GOVERNED_STATIC_BEHAVIOR_DRIFT'
    assert exc_info.value.context['package_emitted'] is False
    assert 'business_rules' in exc_info.value.context['changed_sections']


def test_fonte_com_auto_open_e_shell_nunca_e_executada(monkeypatch, tmp_path):
    marker = tmp_path / 'executed.txt'
    source = (
        'Attribute VB_Name = "modPerigoso"\n'
        'Public Sub Auto_Open()\n'
        f'    Shell "cmd /c echo executed > {marker}"\n'
        'End Sub\n'
    )

    def forbidden(*args, **kwargs):
        raise AssertionError('execucao externa nao permitida')

    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(os, 'system', forbidden)
    monkeypatch.setattr(os, 'startfile', forbidden, raising=False)

    result = evaluate_vba_governed(
        source,
        file_name='modPerigoso.bas',
        version='0.1.0',
    )

    assert result['execution_performed'] is False
    assert not marker.exists()


@pytest.mark.parametrize(
    ('file_name', 'version', 'code'),
    [
        ('../modulo.bas', '0.1.0', 'VBA_GOVERNED_SOURCE_NAME_UNSAFE'),
        ('modulo.cls', '0.1.0', 'VBA_GOVERNED_SOURCE_NAME_UNSAFE'),
        ('modulo.bas', 'v1', 'VBA_GOVERNED_VERSION_INVALID'),
    ],
)
def test_entrada_invalida_falha_com_codigo_claro(file_name, version, code):
    with pytest.raises(VbaGovernedEvaluationError) as exc_info:
        evaluate_vba_governed(_source(), file_name=file_name, version=version)

    assert exc_info.value.code == code


def test_leitor_detecta_corrupcao_de_membro():
    package = _package(_evaluate())
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(package), 'r') as source, zipfile.ZipFile(
        output,
        'w',
        compression=zipfile.ZIP_STORED,
    ) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == 'README.md':
                content += b'corrupted\n'
            target.writestr(info, content)

    with pytest.raises(RuntimeError, match='VBA_GOVERNED_PACKAGE_HASH_MISMATCH'):
        governed._verify_package(output.getvalue())
