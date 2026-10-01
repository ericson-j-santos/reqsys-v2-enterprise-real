from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.vba_legacy as vba_api
import app.services.vba_governed_evaluation as governed
from app.api.vba_legacy import router
from app.core.security import get_current_user, require_admin
from app.main import app as production_app

SOURCE = (
    'Attribute VB_Name = "modAvaliacaoReqSys"\n'
    'Public Sub Avaliar(ByVal valor As Long)\n'
    '    If valor > 10 Then Range("A1").Value = "ALTO"\n'
    'End Sub\n'
).encode('utf-8')
URL = '/api/requisitos/legado/vba/avaliar-versao-controlada'


def _app(*, admin: bool) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix='/api/requisitos')
    if admin:
        app.dependency_overrides[require_admin] = lambda: {'papel': 'admin'}
    return app


def _post(client: TestClient, correlation_id: str):
    return client.post(
        URL,
        data={'versao': '0.1.0'},
        files={'arquivo': ('modAvaliacaoReqSys.bas', SOURCE, 'text/plain')},
        headers={'X-Correlation-Id': correlation_id},
    )


def test_e2e_http_admin_emite_e_rele_pacote_sem_estado_residual():
    client = TestClient(_app(admin=True))
    first = _post(client, 'corr-vba-governed-001')
    second = _post(client, 'corr-vba-governed-002')

    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body['success'] is True
    assert body['meta'] == {
        'correlation_id': 'corr-vba-governed-001',
        'idempotent_evaluation': True,
        'source_persisted': False,
        'execution_performed': False,
        'office_execution': False,
        'functional_equivalence_proven': False,
    }
    assert body['data']['status'] == 'AWAITING_DYNAMIC_VALIDATION'
    assert body['data']['functional_equivalence'] == 'NOT_PROVEN'
    assert body['data']['release_allowed'] is False
    assert body['data']['source_included_in_returned_package'] is True
    assert body['data']['server_persistence_performed'] is False
    assert body['data']['package'] == second.json()['data']['package']

    package_info = body['data']['package']
    package = base64.b64decode(package_info['base64'], validate=True)
    assert hashlib.sha256(package).hexdigest() == package_info['sha256']
    with zipfile.ZipFile(BytesIO(package), 'r') as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('manifest.json'))
        candidate = archive.read('source/candidate/modAvaliacaoReqSys.bas')
        original = archive.read('source/original-normalized/modAvaliacaoReqSys.bas')
    assert manifest['release_allowed'] is False
    assert manifest['functional_equivalence'] == 'NOT_PROVEN'
    assert candidate.count(b'Option Explicit') == 1
    assert original == SOURCE


def test_e2e_http_sem_token_e_rejeitado(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('builder nao pode executar sem autorizacao')

    monkeypatch.setattr(vba_api, 'evaluate_vba_governed', forbidden)
    response = _post(TestClient(_app(admin=False)), 'corr-vba-unauthorized')

    assert response.status_code == 401
    assert response.json()['detail'] == 'Token não fornecido'


def test_e2e_http_usuario_nao_admin_e_rejeitado():
    app = _app(admin=False)
    app.dependency_overrides[get_current_user] = lambda: {'papel': 'analista'}
    response = _post(TestClient(app), 'corr-vba-forbidden')

    assert response.status_code == 403
    assert response.json()['detail'] == 'Acesso restrito a administradores'


def test_rota_de_producao_e_registrada_uma_vez():
    operation = production_app.openapi()['paths'][URL]

    assert set(operation) == {'post'}


def test_e2e_rejeita_office_no_fluxo_de_transformacao():
    client = TestClient(_app(admin=True))
    response = client.post(
        URL,
        data={'versao': '0.1.0'},
        files={'arquivo': ('nao-executar.xlsm', b'PK-fake-office', 'application/octet-stream')},
    )

    assert response.status_code == 422
    assert response.json()['detail']['code'] == (
        'VBA_GOVERNED_TRANSFORMATION_REQUIRES_EXPORTED_BAS'
    )


def test_e2e_segredo_e_bloqueado_sem_vazamento():
    secret = 'segredo-super-critico-123'
    source = f'Public Const API_KEY = "{secret}"\nPublic Sub X()\nEnd Sub\n'.encode()
    response = TestClient(_app(admin=True)).post(
        URL,
        data={'versao': '0.1.0'},
        files={'arquivo': ('segredo.bas', source, 'text/plain')},
    )

    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'VBA_GOVERNED_SECRET_LITERAL_BLOCKED'
    assert response.json()['detail']['package_emitted'] is False
    assert secret not in response.text


def test_e2e_versao_invalida_e_binario_sao_rejeitados():
    client = TestClient(_app(admin=True))
    invalid_version = client.post(
        URL,
        data={'versao': 'v1'},
        files={'arquivo': ('modulo.bas', SOURCE, 'text/plain')},
    )
    binary = client.post(
        URL,
        data={'versao': '0.1.0'},
        files={'arquivo': ('modulo.bas', b'Sub X()\x00End Sub', 'application/octet-stream')},
    )

    assert invalid_version.status_code == 422
    assert invalid_version.json()['detail']['code'] == 'VBA_GOVERNED_VERSION_INVALID'
    assert binary.status_code == 422
    assert binary.json()['detail']['code'] == 'VBA_SOURCE_BINARY_CONTENT'


def test_e2e_limite_do_pacote_e_mapeado_para_413(monkeypatch):
    monkeypatch.setattr(governed, 'MAX_PACKAGE_BYTES', 1)

    response = _post(TestClient(_app(admin=True)), 'corr-vba-package-limit')

    assert response.status_code == 413
    assert response.json()['detail'] == {
        'code': 'VBA_GOVERNED_PACKAGE_TOO_LARGE',
        'max_bytes': 1,
    }
