from __future__ import annotations

import base64
import io
import json
import zipfile

import pytest

from app.services.vba_governed_evaluation import (
    GovernedVbaEvaluationError,
    build_governed_vba_evaluation_package,
)

SOURCE = '''Attribute VB_Name = "Example"
Public Sub CalculateTotal()
    Dim quantity As Long
    Dim price As Currency
    quantity = Range("A1").Value
    price = Range("B1").Value
    If quantity > 0 Then Range("C1").Value = quantity * price
End Sub
'''


def _files(result: dict) -> dict[str, bytes]:
    raw = base64.b64decode(result['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_builds_versioned_deterministic_package_with_static_evidence():
    first = build_governed_vba_evaluation_package(
        SOURCE, file_name='Example.bas', version='1.2.3'
    )
    second = build_governed_vba_evaluation_package(
        SOURCE, file_name='Example.bas', version='1.2.3'
    )

    assert first['package_sha256'] == second['package_sha256']
    assert first['zip_base64'] == second['zip_base64']
    assert first['manifest']['release_allowed'] is False
    assert first['manifest']['dynamic_validation']['status'] == 'future_required'
    assert first['static_evidence']['semantic_signature_preserved'] is True
    assert first['static_evidence']['dynamic_equivalence_proven'] is False

    files = _files(first)
    transformed = files['transformed/Example.bas'].decode('utf-8')
    assert 'Option Explicit' in transformed
    assert 'On Error GoTo ReqSys_Error_' in transformed
    assert 'ReqSys_LogError "Example.CalculateTotal"' in transformed
    assert 'Err.Raise ReqSysErrNumber_' in transformed
    assert 'controls/ReqSysControls.bas' in files
    assert 'checksums.sha256' in files

    manifest = json.loads(files['manifest.json'])
    assert manifest['package_version'] == '1.2.3'
    checksums = files['checksums.sha256'].decode('utf-8')
    assert '  transformed/Example.bas' in checksums
    assert '  manifest.json' in checksums


def test_existing_error_handler_is_not_rewritten_and_blocks_static_gate():
    source = '''Option Explicit
Public Sub ExistingHandler()
    On Error GoTo Handler
    Range("A1").Value = 1
    Exit Sub
Handler:
    MsgBox Err.Description
End Sub
'''
    result = build_governed_vba_evaluation_package(
        source, file_name='Existing.bas', version='0.1.0'
    )

    assert result['static_evidence']['procedure_controls_complete'] is False
    assert result['static_evidence']['passed'] is False
    control = result['manifest']['controls'][1]
    assert control['status'] == 'partial'
    assert control['procedure_decisions'][0]['reason'] == (
        'existing_error_handler_requires_human_review'
    )


@pytest.mark.parametrize('version', ['v1', '1.0', '01.0.0', '../1.0.0'])
def test_rejects_invalid_versions(version):
    with pytest.raises(GovernedVbaEvaluationError) as exc_info:
        build_governed_vba_evaluation_package(
            SOURCE, file_name='Example.bas', version=version
        )
    assert exc_info.value.code == 'VBA_GOVERNED_VERSION_INVALID'


def test_rejects_unterminated_procedure():
    with pytest.raises(GovernedVbaEvaluationError) as exc_info:
        build_governed_vba_evaluation_package(
            'Public Sub Broken()\nRange("A1").Value = 1\n',
            file_name='Broken.bas',
        )
    assert exc_info.value.code == 'VBA_GOVERNED_PROCEDURE_UNTERMINATED'
