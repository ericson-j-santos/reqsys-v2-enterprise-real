"""Testes de caminhos críticos — copilot_studio_provisioner."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas.agents import AgentProvisionRequest
from app.services import copilot_studio_provisioner as provisioner


def _run(coro):
    return asyncio.run(coro)


def _request(**kwargs) -> AgentProvisionRequest:
    base = {
        'name': 'agente-teste',
        'package_type': 'software_lifecycle_orchestrator',
        'target': 'copilot_studio',
    }
    base.update(kwargs)
    return AgentProvisionRequest(**base)


def test_provisionar_dry_run_nao_chama_externo():
    resultado = _run(provisioner.provisionar_copilot_studio(_request(mode='dry_run')))

    assert resultado['configured'] is True
    assert resultado['provisioned'] is False
    assert resultado['mode'] == 'dry_run'
    assert 'generated_files' in resultado['details']


def test_provisionar_webhook_sem_url_configurada(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_provisioning_webhook_url', '')

    resultado = _run(provisioner.provisionar_copilot_studio(_request(mode='webhook')))

    assert resultado['configured'] is False
    assert resultado['provisioned'] is False
    assert 'WEBHOOK_URL' in resultado['message']


def test_provisionar_dataverse_sem_environment_url(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_environment_url', '')

    resultado = _run(
        provisioner.provisionar_copilot_studio(
            _request(mode='dataverse_import', environment_url=None),
        )
    )

    assert resultado['configured'] is False
    assert 'ENVIRONMENT_URL' in resultado['message']


def test_provisionar_dataverse_sem_solution_zip(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_environment_url', 'https://org.crm.dynamics.com/')
    monkeypatch.setattr(provisioner.settings, 'azure_tenant_id', 'tenant')
    monkeypatch.setattr(provisioner.settings, 'azure_client_id', 'client')
    monkeypatch.setattr(provisioner.settings, 'azure_client_secret', 'secret')

    resultado = _run(
        provisioner.provisionar_copilot_studio(
            _request(
                mode='dataverse_import',
                environment_url='https://org.crm.dynamics.com/',
                solution_zip_base64=None,
            ),
        )
    )

    assert resultado['configured'] is True
    assert resultado['provisioned'] is False
    assert 'solution_zip_base64' in resultado['message']


def test_provisionar_webhook_sucesso_mockado(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_provisioning_webhook_url', 'https://flow.example/hook')
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_provisioning_webhook_key', 'api-key')

    fake_response = type(
        'Resp',
        (),
        {
            'status_code': 202,
            'json': lambda self: {'requestId': 'req-1'},
            'text': 'ok',
            'raise_for_status': lambda self: None,
        },
    )()

    with patch.object(provisioner.httpx, 'AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = fake_response
        mock_client_cls.return_value = mock_client

        resultado = _run(provisioner.provisionar_copilot_studio(_request(mode='webhook')))

    assert resultado['configured'] is True
    assert resultado['provisioned'] is True


def test_provisionar_dataverse_sem_credenciais_entra(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_environment_url', 'https://org.crm.dynamics.com/')
    monkeypatch.setattr(provisioner.settings, 'azure_tenant_id', '')

    resultado = _run(
        provisioner.provisionar_copilot_studio(
            _request(mode='dataverse_import', environment_url='https://org.crm.dynamics.com/'),
        )
    )

    assert resultado['configured'] is False
    assert 'Entra ID' in resultado['message']


def test_provisionar_webhook_resposta_nao_json(monkeypatch):
    monkeypatch.setattr(provisioner.settings, 'copilotstudio_provisioning_webhook_url', 'https://flow.example/hook')

    fake_response = type(
        'Resp',
        (),
        {
            'status_code': 200,
            'json': lambda self: (_ for _ in ()).throw(ValueError('not json')),
            'text': 'plain text ok',
            'raise_for_status': lambda self: None,
        },
    )()

    with patch.object(provisioner.httpx, 'AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = fake_response
        mock_client_cls.return_value = mock_client

        resultado = _run(provisioner.provisionar_copilot_studio(_request(mode='webhook')))

    assert resultado['provisioned'] is True
    assert resultado['details']['webhook_response']['text'] == 'plain text ok'


def test_provisionar_dataverse_import_sucesso_mockado(monkeypatch):
    import base64

    monkeypatch.setattr(provisioner.settings, 'copilotstudio_environment_url', 'https://org.crm.dynamics.com/')
    monkeypatch.setattr(provisioner.settings, 'azure_tenant_id', 'tenant')
    monkeypatch.setattr(provisioner.settings, 'azure_client_id', 'client')
    monkeypatch.setattr(provisioner.settings, 'azure_client_secret', 'secret')

    token_response = type(
        'Resp',
        (),
        {
            'raise_for_status': lambda self: None,
            'json': lambda self: {'access_token': 'token-abc'},
        },
    )()
    import_response = type(
        'Resp',
        (),
        {
            'status_code': 204,
            'raise_for_status': lambda self: None,
            'json': lambda self: (_ for _ in ()).throw(ValueError('empty')),
            'text': '',
        },
    )()

    with patch.object(provisioner.httpx, 'AsyncClient') as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = [token_response, import_response]
        mock_client_cls.return_value = mock_client

        resultado = _run(
            provisioner.provisionar_copilot_studio(
                _request(
                    mode='dataverse_import',
                    environment_url='https://org.crm.dynamics.com/',
                    solution_zip_base64=base64.b64encode(b'zip-content').decode(),
                ),
            )
        )

    assert resultado['provisioned'] is True
    assert resultado['details']['dataverse_status'] == 204
