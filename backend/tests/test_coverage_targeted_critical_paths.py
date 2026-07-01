"""Testes Pareto para elevar coverage de módulos críticos de integração."""

import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import jwt
import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api import async_workflows
from app.services import azure_auth, figma_client
from app.services.async_workflow_jobs import (
    AsyncWorkflowJobRequest,
    WorkflowJobStatus,
    store,
)


class _FakeResponse:
    def __init__(self, body: str = '{"ok": true}', status: int = 200):
        self.body = body.encode('utf-8')
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def test_figma_request_json_monta_headers_e_payload(monkeypatch):
    monkeypatch.setattr(figma_client.settings, 'figma_access_token', 'figma-token')
    captured = {}

    def fake_urlopen(req, timeout):
        captured['timeout'] = timeout
        captured['method'] = req.get_method()
        captured['url'] = req.full_url
        captured['body'] = json.loads(req.data.decode('utf-8'))
        captured['token'] = req.headers['X-figma-token']
        captured['content_type'] = req.headers['Content-type']
        return _FakeResponse('{"id": "comment-1"}')

    monkeypatch.setattr(figma_client.request, 'urlopen', fake_urlopen)

    response = figma_client._request_json('POST', '/v1/files/file/comments', {'message': 'ok'})

    assert response == {'id': 'comment-1'}
    assert captured == {
        'timeout': 20,
        'method': 'POST',
        'url': 'https://api.figma.com/v1/files/file/comments',
        'body': {'message': 'ok'},
        'token': 'figma-token',
        'content_type': 'application/json',
    }


def test_figma_request_json_sem_token_bloqueia_chamada(monkeypatch):
    monkeypatch.setattr(figma_client.settings, 'figma_access_token', '  ')

    with pytest.raises(figma_client.FigmaError, match='FIGMA_ACCESS_TOKEN'):
        figma_client._request_json('GET', '/v1/files/file')


def test_figma_request_json_normaliza_erros_http_e_rede(monkeypatch):
    monkeypatch.setattr(figma_client.settings, 'figma_access_token', 'figma-token')

    http_error = HTTPError(
        url='https://api.figma.com/v1/files/file',
        code=403,
        msg='Forbidden',
        hdrs=None,
        fp=io.BytesIO(b'{"err":"denied"}'),
    )
    monkeypatch.setattr(figma_client.request, 'urlopen', lambda req, timeout: (_ for _ in ()).throw(http_error))

    with pytest.raises(figma_client.FigmaError, match='HTTP 403 no Figma'):
        figma_client._request_json('GET', '/v1/files/file')

    monkeypatch.setattr(
        figma_client.request,
        'urlopen',
        lambda req, timeout: (_ for _ in ()).throw(URLError('offline')),
    )

    with pytest.raises(figma_client.FigmaError, match='Falha de rede no Figma'):
        figma_client._request_json('GET', '/v1/files/file')


def test_azure_validar_token_tenta_issuer_v1_e_aceita_v2(monkeypatch):
    key = SimpleNamespace(key='public-key')
    client = SimpleNamespace(get_signing_key_from_jwt=lambda token: key)
    monkeypatch.setattr(azure_auth, '_get_jwks_client', lambda tenant_id: client)
    calls = []

    def fake_decode(id_token, signing_key, algorithms, audience, issuer, options):
        calls.append({'issuer': issuer, 'audience': audience, 'options': options})
        if issuer.startswith('https://sts.windows.net/'):
            raise jwt.exceptions.InvalidIssuerError('issuer mismatch')
        return {'sub': 'user-1', 'iss': issuer}

    monkeypatch.setattr(azure_auth.jwt, 'decode', fake_decode)

    claims = azure_auth.validar_token_azure('token', 'tenant-id', 'client-id')

    assert claims == {'sub': 'user-1', 'iss': 'https://login.microsoftonline.com/tenant-id/v2.0'}
    assert [call['issuer'] for call in calls] == [
        'https://sts.windows.net/tenant-id/',
        'https://login.microsoftonline.com/tenant-id/v2.0',
    ]
    assert calls[0]['audience'] == 'client-id'
    assert calls[0]['options'] == {'verify_nbf': True}


def test_azure_validar_token_reporta_falha_jwks(monkeypatch):
    def fail_jwks(tenant_id):
        raise RuntimeError('jwks indisponivel')

    monkeypatch.setattr(azure_auth, '_get_jwks_client', fail_jwks)

    with pytest.raises(ValueError, match='Token inválido ou não reconhecido pelo Azure AD'):
        azure_auth.validar_token_azure('token', 'tenant-id', 'client-id')


@pytest.mark.asyncio
async def test_async_workflow_health_e_consulta_job_inexistente():
    health = await async_workflows.async_workflow_health()
    assert health['status'] == 'ok'
    assert health['enterprise_upgrade_path'] == ['redis', 'rabbitmq', 'azure_service_bus']

    with pytest.raises(HTTPException) as exc_info:
        await async_workflows.consultar_job_assincrono('job-inexistente')

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_async_workflow_cria_job_com_correlation_id_e_status_url(monkeypatch):
    monkeypatch.setattr(async_workflows, 'process_async_workflow_job', lambda job_id: None)
    background_tasks = BackgroundTasks()
    payload = AsyncWorkflowJobRequest(destino_url='https://example.com/hook', payload={'ok': True})

    response = await async_workflows.criar_job_assincrono(payload, background_tasks, x_correlation_id=' corr-123 ')
    stored = await store.get(response['job_id'])

    assert response['status'] == WorkflowJobStatus.QUEUED.value
    assert response['correlation_id'] == 'corr-123'
    assert response['status_url'] == f"/api/workflows/async-httpx/jobs/{response['job_id']}"
    assert stored is not None
    assert stored.request.payload == {'ok': True}
    assert len(background_tasks.tasks) == 1
