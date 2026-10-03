from __future__ import annotations

import base64
import io
import json
import zipfile

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.vba_legacy import evaluate_vba_controls
from app.core.security import require_admin
from app.main import app


@pytest.mark.asyncio
async def test_api_runs_analysis_control_application_and_packaging():
    source = b'''Attribute VB_Name = "Example"
Public Sub RunExample()
    If Range("A1").Value > 0 Then Range("B1").Value = "ok"
End Sub
'''
    response = await evaluate_vba_controls(
        arquivo=UploadFile(filename='Example.bas', file=io.BytesIO(source)),
        version='2.0.0',
        user={'role': 'admin'},
        x_correlation_id='vba-e2e-positive',
    )

    assert response['success'] is True
    assert response['meta']['correlation_id'] == 'vba-e2e-positive'
    assert response['meta']['execution_performed'] is False
    assert response['data']['static_evidence']['passed'] is True
    raw = base64.b64decode(response['data']['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        assert archive.testzip() is None
        assert 'manifest.json' in archive.namelist()
        assert 'transformed/Example.bas' in archive.namelist()


@pytest.mark.asyncio
async def test_api_fails_closed_for_office_container_transformation():
    with pytest.raises(HTTPException) as exc_info:
        await evaluate_vba_controls(
            arquivo=UploadFile(filename='Unsafe.xlsm', file=io.BytesIO(b'not-office')),
            version='1.0.0',
            user={'role': 'admin'},
            x_correlation_id='vba-e2e-negative',
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail['code'] == 'VBA_GOVERNED_SOURCE_EXPORT_REQUIRED'


def test_http_e2e_returns_downloadable_package_for_unique_correlation_id():
    app.dependency_overrides[require_admin] = lambda: {'role': 'admin'}
    try:
        client = TestClient(app)
        response = client.post(
            '/api/requisitos/legado/vba/avaliar-controles?version=3.0.0',
            files={
                'arquivo': (
                    'HttpExample.bas',
                    b'Public Sub HttpExample()\nRange("A1").Value = 1\nEnd Sub\n',
                    'application/octet-stream',
                )
            },
            headers={'X-Correlation-Id': 'vba-http-e2e-unique-001'},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['meta']['correlation_id'] == 'vba-http-e2e-unique-001'
    assert payload['data']['package_version'] == '3.0.0'
    assert payload['data']['static_evidence']['passed'] is True
    raw = base64.b64decode(payload['data']['zip_base64'])
    with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read('manifest.json'))['release_allowed'] is False
