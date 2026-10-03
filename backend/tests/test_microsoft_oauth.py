from __future__ import annotations

import json

import httpx
import pytest

from app.services.microsoft_oauth import (
    MicrosoftOAuthError,
    acquire_client_credentials_token,
)


@pytest.mark.asyncio
async def test_oauth_error_preserva_so_diagnostico_allowlisted():
    request = httpx.Request('POST', 'https://login.microsoftonline.com/tenant/oauth2/v2.0/token')
    response = httpx.Response(
        401,
        request=request,
        json={
            'error': 'invalid_client',
            'error_description': 'AADSTS7000222: secret-super-sensivel expirou',
            'error_codes': [7000222],
            'trace_id': 'trace-123',
            'correlation_id': 'corr-456',
            'timestamp': '2026-10-01T12:00:00Z',
            'client_secret': 'secret-super-sensivel',
        },
    )

    class Client:
        async def post(self, *args, **kwargs):
            return response

    with pytest.raises(MicrosoftOAuthError) as captured:
        await acquire_client_credentials_token(
            client=Client(),
            tenant_id='tenant',
            client_id='client',
            client_secret='secret-super-sensivel',
            scope='https://api.powerplatform.com/.default',
            resource='power_platform',
        )

    detail = captured.value.as_dict()
    assert detail['status_code'] == 401
    assert detail['error_code'] == 'invalid_client'
    assert detail['aadsts_code'] == 'AADSTS7000222'
    assert detail['trace_id'] == 'trace-123'
    assert detail['correlation_id'] == 'corr-456'
    serialized = json.dumps(detail) + str(captured.value)
    assert 'secret-super-sensivel' not in serialized
    assert 'error_description' not in serialized


@pytest.mark.asyncio
async def test_oauth_token_usa_client_credentials_sem_logar_token():
    request = httpx.Request('POST', 'https://login.microsoftonline.com/tenant/oauth2/v2.0/token')
    response = httpx.Response(200, request=request, json={'access_token': 'token-super-sensivel'})

    class Client:
        call: dict | None = None

        async def post(self, url, **kwargs):
            self.call = {'url': url, **kwargs}
            return response

    client = Client()
    token = await acquire_client_credentials_token(
        client=client,
        tenant_id='tenant',
        client_id='client',
        client_secret='secret',
        scope='https://org.crm.dynamics.com/.default',
        resource='dataverse',
    )

    assert token == 'token-super-sensivel'
    assert client.call is not None
    assert client.call['data']['grant_type'] == 'client_credentials'
    assert client.call['data']['scope'] == 'https://org.crm.dynamics.com/.default'
