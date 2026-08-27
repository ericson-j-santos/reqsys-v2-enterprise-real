from __future__ import annotations

import base64
import gzip
import json
import uuid
from copy import deepcopy
from typing import Any

import httpx

from app.core.config import settings
from copilot_memory_powerautomate_complete import (
    gerar_fluxos_completos,
    validar_definicao,
)
from copilot_memory_simple_package import gerar_planilha_xlsx

_POWER_PLATFORM_BASE = 'https://api.powerplatform.com'
_GRAPH_BASE = 'https://graph.microsoft.com/v1.0'
_ALM_WORKFLOW = 'power-automate-flow-provisioning-p0.yml'
_DEFAULT_ALM_REPO = 'ericson-j-santos/reqsys-powerplatform-alm'


def _credenciais_microsoft_configuradas() -> bool:
    return bool(settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret)


async def _token(scope: str) -> str:
    if not _credenciais_microsoft_configuradas():
        raise RuntimeError('Credenciais Microsoft Entra nao configuradas no ReqSys')
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f'https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': scope,
            },
        )
        response.raise_for_status()
        return response.json()['access_token']


async def listar_ambientes_instalacao() -> dict[str, Any]:
    if not _credenciais_microsoft_configuradas():
        return {'configurado': False, 'ambientes': [], 'erro': 'Credenciais Microsoft Entra nao configuradas'}
    try:
        token = await _token('https://api.powerplatform.com/.default')
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{_POWER_PLATFORM_BASE}/environmentmanagement/environments?api-version=2024-10-01',
                headers={'Authorization': f'Bearer {token}'},
            )
            response.raise_for_status()
        ambientes = []
        for item in response.json().get('value', []):
            ambientes.append(
                {
                    'id': item.get('id'),
                    'nome': item.get('displayName') or item.get('id'),
                    'url': item.get('url') or '',
                    'estado': item.get('state') or '',
                    'tipo': item.get('type') or '',
                    'regiao': item.get('geo') or item.get('azureRegion') or '',
                }
            )
        return {'configurado': True, 'ambientes': ambientes, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'ambientes': [], 'erro': str(exc)}


async def listar_planos_instalacao(group_id: str) -> dict[str, Any]:
    if not group_id.strip():
        return {'configurado': _credenciais_microsoft_configuradas(), 'planos': [], 'erro': 'Group ID obrigatorio'}
    try:
        token = await _token('https://graph.microsoft.com/.default')
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{_GRAPH_BASE}/groups/{group_id.strip()}/planner/plans',
                headers={'Authorization': f'Bearer {token}'},
            )
            response.raise_for_status()
        planos = [
            {'id': item.get('id'), 'titulo': item.get('title') or item.get('id')}
            for item in response.json().get('value', [])
        ]
        return {'configurado': True, 'planos': planos, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'planos': [], 'erro': str(exc)}


async def listar_arquivos_excel_grupo(group_id: str) -> dict[str, Any]:
    if not group_id.strip():
        return {'configurado': _credenciais_microsoft_configuradas(), 'arquivos': [], 'erro': 'Group ID obrigatorio'}
    try:
        token = await _token('https://graph.microsoft.com/.default')
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(timeout=20) as client:
            drive_response = await client.get(f'{_GRAPH_BASE}/groups/{group_id.strip()}/drive', headers=headers)
            drive_response.raise_for_status()
            drive = drive_response.json()
            files_response = await client.get(
                f'{_GRAPH_BASE}/groups/{group_id.strip()}/drive/root/children',
                headers=headers,
                params={'$select': 'id,name,webUrl,file,parentReference'},
            )
            files_response.raise_for_status()
        arquivos = []
        for item in files_response.json().get('value', []):
            name = str(item.get('name') or '')
            if not name.lower().endswith('.xlsx'):
                continue
            arquivos.append(
                {
                    'id': item.get('id'),
                    'nome': name,
                    'web_url': item.get('webUrl') or '',
                    'drive_id': drive.get('id') or item.get('parentReference', {}).get('driveId') or '',
                    'excel_source': f'groups/{group_id.strip()}',
                }
            )
        return {'configurado': True, 'arquivos': arquivos, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'arquivos': [], 'erro': str(exc)}


async def criar_planilha_excel_grupo(group_id: str, nome: str = 'CopilotMemory.xlsx') -> dict[str, Any]:
    if not group_id.strip():
        raise ValueError('Group ID obrigatorio')
    safe_name = (nome or 'CopilotMemory.xlsx').strip()
    if not safe_name.lower().endswith('.xlsx'):
        raise ValueError('O arquivo deve terminar com .xlsx')
    token = await _token('https://graph.microsoft.com/.default')
    xlsx = gerar_planilha_xlsx()
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.put(
            f'{_GRAPH_BASE}/groups/{group_id.strip()}/drive/root:/{safe_name}:/content',
            headers=headers,
            content=xlsx,
        )
        response.raise_for_status()
        item = response.json()
        drive_response = await client.get(
            f'{_GRAPH_BASE}/groups/{group_id.strip()}/drive',
            headers={'Authorization': f'Bearer {token}'},
        )
        drive_response.raise_for_status()
    return {
        'id': item.get('id'),
        'nome': item.get('name') or safe_name,
        'web_url': item.get('webUrl') or '',
        'drive_id': drive_response.json().get('id') or '',
        'excel_source': f'groups/{group_id.strip()}',
    }


async def listar_conexoes_instalacao(environment_id: str) -> dict[str, Any]:
    if not environment_id.strip():
        return {'configurado': _credenciais_microsoft_configuradas(), 'planner': [], 'excel': [], 'erro': 'Ambiente obrigatorio'}
    try:
        token = await _token('https://api.powerplatform.com/.default')
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f'{_POWER_PLATFORM_BASE}/connectivity/environments/{environment_id.strip()}/connections',
                headers={'Authorization': f'Bearer {token}'},
                params={'api-version': '2024-10-01'},
            )
            response.raise_for_status()
        planner: list[dict[str, Any]] = []
        excel: list[dict[str, Any]] = []
        for item in response.json().get('value', []):
            props = item.get('properties') or {}
            api_id = str(props.get('apiId') or props.get('connectorId') or item.get('type') or '')
            normalized = {
                'id': item.get('name') or item.get('id'),
                'recurso_id': item.get('id') or '',
                'nome': props.get('displayName') or item.get('name') or item.get('id'),
                'api_id': api_id,
            }
            low = api_id.lower()
            if 'shared_planner' in low:
                planner.append(normalized)
            if 'shared_excelonlinebusiness' in low:
                excel.append(normalized)
        return {'configurado': True, 'planner': planner, 'excel': excel, 'erro': None}
    except Exception as exc:
        return {'configurado': True, 'planner': [], 'excel': [], 'erro': str(exc)}


def _parametrizar_definicao(definition: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(definition)
    params = result.setdefault('parameters', {})
    values = {
        'PLANNER_GROUP_ID': payload['group_id'],
        'PLANNER_PLAN_ID': payload['plan_id'],
        'EXCEL_SOURCE': payload['excel_source'],
        'EXCEL_DRIVE': payload['excel_drive'],
        'EXCEL_FILE': payload['excel_file'],
    }
    for key, value in values.items():
        if key not in params:
            params[key] = {'type': 'String'}
        params[key]['defaultValue'] = value
    return result


def montar_bundle_implantacao(payload: dict[str, Any]) -> dict[str, Any]:
    flows = []
    for flow in gerar_fluxos_completos():
        definition = _parametrizar_definicao(flow['definition'], payload)
        errors = validar_definicao(definition)
        if errors:
            raise ValueError(f"Definicao invalida em {flow['id']}: {errors}")
        flows.append(
            {
                'id': flow['id'],
                'flow_guid': str(uuid.uuid5(uuid.NAMESPACE_URL, f"copilot-memory:{flow['id']}")),
                'display_name': flow['display_name'],
                'state': 'Stopped',
                'definition': definition,
            }
        )
    return {
        'schema_version': '1.0.0',
        'capability': 'Copilot Memory Installation Assistant',
        'correlation_id': payload.get('correlation_id') or str(uuid.uuid4()),
        'target': {
            'environment_id': payload['environment_id'],
            'environment_url': payload['environment_url'],
            'target_environment': payload.get('target_environment') or 'dev',
        },
        'connections': {
            'planner': payload['planner_connection_id'],
            'excel': payload['excel_connection_id'],
        },
        'flows': flows,
    }


def _compactar_bundle(bundle: dict[str, Any]) -> str:
    raw = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode('ascii')


async def status_assistente_instalacao() -> dict[str, Any]:
    microsoft = _credenciais_microsoft_configuradas()
    ambientes = await listar_ambientes_instalacao() if microsoft else {'configurado': False, 'ambientes': [], 'erro': None}
    alm_repo = settings.github_alm_repo or _DEFAULT_ALM_REPO
    return {
        'microsoft_configurado': microsoft,
        'alm_configurado': bool(settings.github_pat and alm_repo),
        'alm_repository': alm_repo,
        'workflow_file': _ALM_WORKFLOW,
        'ambientes': ambientes.get('ambientes', []),
        'erro_ambientes': ambientes.get('erro'),
        'manual_boundary': 'autorizar conexoes Planner e Excel quando o tenant exigir consentimento interativo',
    }


async def despachar_implantacao(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get('confirmar'):
        return {'dispatched': False, 'status': 'aguardando_confirmacao', 'bundle': montar_bundle_implantacao(payload)}
    if not settings.github_pat:
        return {'dispatched': False, 'status': 'pending_configuration', 'erro': 'GITHUB_PAT nao configurado no ReqSys'}
    bundle = montar_bundle_implantacao(payload)
    encoded = _compactar_bundle(bundle)
    if len(encoded) > 60000:
        raise ValueError('Bundle de implantacao excede o limite seguro do dispatch')
    repo = settings.github_alm_repo or _DEFAULT_ALM_REPO
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{_ALM_WORKFLOW}/dispatches'
    request = {
        'ref': 'main',
        'inputs': {
            'bundle_base64': encoded,
            'environment_url': payload['environment_url'],
            'environment_id': payload['environment_id'],
            'planner_connection_id': payload['planner_connection_id'],
            'excel_connection_id': payload['excel_connection_id'],
            'correlation_id': bundle['correlation_id'],
            'dry_run': 'false',
        },
    }
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {settings.github_pat}',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=request, headers=headers)
    if response.status_code != 204:
        return {
            'dispatched': False,
            'status': 'erro_dispatch',
            'status_code': response.status_code,
            'erro': response.text[:500],
            'correlation_id': bundle['correlation_id'],
        }
    return {
        'dispatched': True,
        'status': 'implantacao_solicitada',
        'correlation_id': bundle['correlation_id'],
        'workflow_url': f'https://github.com/{repo}/actions/workflows/{_ALM_WORKFLOW}',
        'flows': [flow['display_name'] for flow in bundle['flows']],
    }
