from __future__ import annotations

import base64
import uuid
from typing import Any

import httpx
from app.core.config import settings
from app.schemas.agents import AgentProvisionRequest
from app.services.agent_generator import PACKAGE_NAME, gerar_pacote_agentes

_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'


def _normalizar_env_url(value: str | None) -> str:
    env_url = (value or settings.copilotstudio_environment_url or '').strip()
    if not env_url:
        return ''
    return env_url.rstrip('/') + '/'


def _tem_credenciais_entra() -> bool:
    return bool(settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret)


async def _token_dataverse(env_url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _TOKEN_URL.format(tenant=settings.azure_tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': env_url.rstrip('/') + '/.default',
            },
        )
        resp.raise_for_status()
        return resp.json()['access_token']


async def _provisionar_via_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    webhook_url = settings.copilotstudio_provisioning_webhook_url
    if not webhook_url:
        return {
            'configured': False,
            'provisioned': False,
            'message': 'COPILOTSTUDIO_PROVISIONING_WEBHOOK_URL nao configurado.',
            'details': {'expected_setting': 'COPILOTSTUDIO_PROVISIONING_WEBHOOK_URL'},
        }

    headers = {'Content-Type': 'application/json'}
    if settings.copilotstudio_provisioning_webhook_key:
        headers['x-api-key'] = settings.copilotstudio_provisioning_webhook_key

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(webhook_url, json=payload, headers=headers)
        resp.raise_for_status()
        try:
            response_body: Any = resp.json()
        except ValueError:
            response_body = {'status_code': resp.status_code, 'text': resp.text[:1000]}

    return {
        'configured': True,
        'provisioned': True,
        'message': 'Solicitacao enviada ao conector/webhook de provisionamento do Copilot Studio.',
        'details': {'webhook_status': resp.status_code, 'webhook_response': response_body},
    }


async def _importar_solution_dataverse(request: AgentProvisionRequest, package: dict[str, Any]) -> dict[str, Any]:
    env_url = _normalizar_env_url(request.environment_url)
    if not env_url:
        return {
            'configured': False,
            'provisioned': False,
            'message': 'COPILOTSTUDIO_ENVIRONMENT_URL ou environment_url nao configurado.',
            'details': {'expected_setting': 'COPILOTSTUDIO_ENVIRONMENT_URL'},
        }

    if not _tem_credenciais_entra():
        return {
            'configured': False,
            'provisioned': False,
            'message': 'Credenciais Entra ID nao configuradas para Dataverse.',
            'details': {
                'expected_settings': ['AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET'],
            },
        }

    # ImportSolution exige um ZIP de solution Power Platform valido. O pacote gerado
    # pela API e um kit Copilot Studio; por isso aceitamos solution_zip_base64
    # explicitamente para importacao real.
    solution_b64 = request.solution_zip_base64
    if not solution_b64:
        return {
            'configured': True,
            'provisioned': False,
            'message': (
                'Dataverse ImportSolution requer um ZIP de solution Power Platform valido. '
                'Envie solution_zip_base64 exportado do Copilot Studio/Power Platform ALM.'
            ),
            'details': {
                'environment_url': env_url,
                'generated_package_files': [file['path'] for file in package['files']],
                'next_step': 'Empacote uma solution Copilot Studio valida e reenvie em solution_zip_base64.',
            },
        }

    # Falha cedo se base64 vier quebrado, antes de chamar a Microsoft.
    base64.b64decode(solution_b64, validate=True)

    token = await _token_dataverse(env_url)
    payload = {
        'CustomizationFile': solution_b64,
        'OverwriteUnmanagedCustomizations': request.overwrite_unmanaged_customizations,
        'PublishWorkflows': request.publish_workflows,
        'ImportJobId': str(uuid.uuid4()),
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'OData-MaxVersion': '4.0',
        'OData-Version': '4.0',
    }

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f'{env_url}api/data/v9.2/ImportSolution', json=payload, headers=headers)
        resp.raise_for_status()
        try:
            response_body: Any = resp.json()
        except ValueError:
            response_body = {'status_code': resp.status_code, 'text': resp.text[:1000]}

    return {
        'configured': True,
        'provisioned': True,
        'message': 'Solution enviada ao Dataverse ImportSolution.',
        'details': {
            'environment_url': env_url,
            'import_job_id': payload['ImportJobId'],
            'dataverse_status': resp.status_code,
            'dataverse_response': response_body,
        },
    }


async def provisionar_copilot_studio(request: AgentProvisionRequest) -> dict[str, Any]:
    package = gerar_pacote_agentes(request)
    payload = {
        'agent': {
            'name': request.name,
            'package_type': request.package_type,
            'target': request.target,
            'language': request.language,
        },
        'package': package,
    }

    if request.mode == 'dry_run':
        result = {
            'configured': True,
            'provisioned': False,
            'message': 'Dry-run concluido. Nenhuma chamada externa foi executada.',
            'details': {
                'available_modes': ['webhook', 'dataverse_import'],
                'generated_files': [file['path'] for file in package['files']],
            },
        }
    elif request.mode == 'webhook':
        result = await _provisionar_via_webhook(payload)
    else:
        result = await _importar_solution_dataverse(request, package)

    return {
        'configured': result['configured'],
        'provisioned': result['provisioned'],
        'mode': request.mode,
        'target': request.target,
        'package_name': PACKAGE_NAME,
        'message': result['message'],
        'details': result.get('details', {}),
    }
