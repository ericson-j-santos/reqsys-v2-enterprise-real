from __future__ import annotations

import base64
import gzip
import json
import uuid
from typing import Any, Iterator

import httpx

from app.core.config import settings

PROFILE = 'wsjf_planner_excel_simples'
WORKFLOW_FILE = 'wsjf-planner-excel-provisioning.yml'
DEFAULT_ALM_REPO = 'ericson-j-santos/reqsys-powerplatform-alm'
SCHEMA = 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
PLANNER_API = '/providers/Microsoft.PowerApps/apis/shared_planner'
EXCEL_API = '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness'
TABLE = 'tbDemandas'
LOCAL_FIELDS = {
    'Bloqueado',
    'Descrição do bloqueio',
    'Próxima ação',
    'Risco',
    'Observações',
}


def _parameters(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        '$authentication': {'defaultValue': {}, 'type': 'SecureObject'},
        '$connections': {'defaultValue': {}, 'type': 'Object'},
        'PLANNER_GROUP_ID': {'defaultValue': payload['group_id'], 'type': 'String'},
        'PLANNER_PLAN_ID': {'defaultValue': payload['plan_id'], 'type': 'String'},
        'EXCEL_SOURCE': {'defaultValue': payload['excel_source'], 'type': 'String'},
        'EXCEL_DRIVE': {'defaultValue': payload['excel_drive'], 'type': 'String'},
        'EXCEL_FILE': {'defaultValue': payload['excel_file'], 'type': 'String'},
    }


def _openapi(
    api_id: str,
    connection_name: str,
    operation_id: str,
    parameters: dict[str, Any],
    *,
    run_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'type': 'OpenApiConnection',
        'inputs': {
            'parameters': parameters,
            'host': {
                'apiId': api_id,
                'operationId': operation_id,
                'connectionName': connection_name,
            },
        },
        'runAfter': run_after or {},
    }


def _excel(operation: str, parameters: dict[str, Any], *, run_after: dict[str, Any] | None = None) -> dict[str, Any]:
    return _openapi(EXCEL_API, 'shared_excelonlinebusiness', operation, parameters, run_after=run_after)


def _planner(operation: str, parameters: dict[str, Any], *, run_after: dict[str, Any] | None = None) -> dict[str, Any]:
    return _openapi(PLANNER_API, 'shared_planner', operation, parameters, run_after=run_after)


def _excel_base() -> dict[str, Any]:
    return {
        'source': "@parameters('EXCEL_SOURCE')",
        'drive': "@parameters('EXCEL_DRIVE')",
        'file': "@parameters('EXCEL_FILE')",
        'table': TABLE,
    }


def _campos_sincronizados() -> dict[str, Any]:
    return {
        'TaskId': "@items('Para_cada_tarefa')?['id']",
        'Título': "@items('Para_cada_tarefa')?['title']",
        'Bucket': "@items('Para_cada_tarefa')?['bucketId']",
        'Progresso': "@div(float(coalesce(items('Para_cada_tarefa')?['percentComplete'],0)),100)",
        'Prioridade': "@items('Para_cada_tarefa')?['priority']",
        'Responsáveis': "@string(coalesce(items('Para_cada_tarefa')?['assignments'],json('{}')))",
        'Início': "@items('Para_cada_tarefa')?['startDateTime']",
        'Vencimento': "@items('Para_cada_tarefa')?['dueDateTime']",
        'Sincronizado em': '@utcNow()',
    }


def gerar_definicao(payload: dict[str, Any]) -> dict[str, Any]:
    listar_tarefas = _planner(
        'ListTasks_V3',
        {
            'groupId': "@parameters('PLANNER_GROUP_ID')",
            'id': "@parameters('PLANNER_PLAN_ID')",
        },
    )
    listar_linhas = _excel(
        'GetItems',
        {**_excel_base()},
        run_after={'Listar_tarefas': ['Succeeded']},
    )

    filtrar_linha = {
        'type': 'Query',
        'inputs': {
            'from': "@body('Listar_linhas')?['value']",
            'where': "@equals(item()?['TaskId'],items('Para_cada_tarefa')?['id'])",
        },
        'runAfter': {},
    }

    criar_item = {
        **_campos_sincronizados(),
        'Última alteração': '',
        'Link Planner': '',
        'Bloqueado': 'Não',
        'Descrição do bloqueio': '',
        'Próxima ação': '',
        'Risco': '',
        'Observações': '',
    }
    criar = _excel(
        'AddRowV2',
        {**_excel_base(), 'item': criar_item},
    )
    atualizar = _excel(
        'PatchItem',
        {
            **_excel_base(),
            'idColumn': 'TaskId',
            'id': "@items('Para_cada_tarefa')?['id']",
            'item': _campos_sincronizados(),
        },
    )
    upsert = {
        'type': 'If',
        'expression': "@empty(body('Filtrar_linha_existente'))",
        'actions': {'Adicionar_linha': criar},
        'else': {'actions': {'Atualizar_linha': atualizar}},
        'runAfter': {'Filtrar_linha_existente': ['Succeeded']},
    }
    foreach = {
        'type': 'Foreach',
        'foreach': "@body('Listar_tarefas')?['value']",
        'actions': {
            'Filtrar_linha_existente': filtrar_linha,
            'Criar_ou_atualizar': upsert,
        },
        'runAfter': {'Listar_linhas': ['Succeeded']},
    }
    return {
        '$schema': SCHEMA,
        'contentVersion': '1.0.0.0',
        'parameters': _parameters(payload),
        'triggers': {
            'Recorrencia': {
                'type': 'Recurrence',
                'recurrence': {'frequency': 'Hour', 'interval': 1},
            }
        },
        'actions': {
            'Listar_tarefas': listar_tarefas,
            'Listar_linhas': listar_linhas,
            'Para_cada_tarefa': foreach,
        },
    }


def _walk_actions(actions: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for name, action in actions.items():
        yield name, action
        nested = action.get('actions')
        if isinstance(nested, dict):
            yield from _walk_actions(nested)
        else_actions = action.get('else', {}).get('actions')
        if isinstance(else_actions, dict):
            yield from _walk_actions(else_actions)


def validar_definicao(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if definition.get('$schema') != SCHEMA:
        errors.append('schema_invalido')
    raw = json.dumps(definition, ensure_ascii=False)
    if TABLE not in raw:
        errors.append('tabela_tbDemandas_ausente')
    if 'UpdateTask_V2' in raw or 'UpdateTask_V3' in raw:
        errors.append('escrita_planner_proibida')
    for name, action in _walk_actions(definition.get('actions', {})):
        if action.get('type') != 'OpenApiConnection':
            continue
        host = action.get('inputs', {}).get('host', {})
        if host.get('apiId') not in {PLANNER_API, EXCEL_API}:
            errors.append(f'conector_nao_permitido:{name}')
    patch_items = [
        action.get('inputs', {}).get('parameters', {}).get('item', {})
        for _, action in _walk_actions(definition.get('actions', {}))
        if action.get('type') == 'OpenApiConnection'
        and action.get('inputs', {}).get('host', {}).get('operationId') == 'PatchItem'
    ]
    for item in patch_items:
        touched = LOCAL_FIELDS.intersection(item.keys())
        if touched:
            errors.append(f'campo_local_sobrescrito:{sorted(touched)}')
    return errors


def montar_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get('target_environment') or 'dev').strip().lower()
    if target not in {'dev', 'development'}:
        raise ValueError('O perfil wsjf_planner_excel_simples está restrito a DEV neste incremento')
    definition = gerar_definicao(payload)
    errors = validar_definicao(definition)
    if errors:
        raise ValueError(f'Definicao WSJF invalida: {errors}')
    correlation_id = payload.get('correlation_id') or str(uuid.uuid4())
    flow_guid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'reqsys:wsjf:planner-excel-simples:v1'))
    return {
        'schema_version': '1.0.0',
        'profile': PROFILE,
        'capability': 'WSJF Planner Excel Simple Provisioning',
        'correlation_id': correlation_id,
        'target': {
            'environment_id': payload['environment_id'],
            'environment_url': payload['environment_url'],
            'target_environment': 'dev',
        },
        'excel': {
            'source': payload['excel_source'],
            'drive': payload['excel_drive'],
            'file': payload['excel_file'],
            'table': TABLE,
            'planner_is_source_of_truth': True,
            'local_fields_preserved': sorted(LOCAL_FIELDS),
        },
        'connections': {
            'planner': payload['planner_connection_id'],
            'excel': payload['excel_connection_id'],
        },
        'flows': [
            {
                'id': '01_wsjf_planner_para_excel',
                'flow_guid': flow_guid,
                'display_name': 'ReqSys WSJF - Planner para Excel',
                'state': 'Stopped',
                'definition': definition,
            }
        ],
    }


def _compactar(bundle: dict[str, Any]) -> str:
    raw = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode('ascii')


async def despachar(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = montar_bundle(payload)
    if not payload.get('confirmar'):
        return {
            'dispatched': False,
            'status': 'validado_sem_implantar',
            'correlation_id': bundle['correlation_id'],
            'bundle': bundle,
        }
    if not settings.github_pat:
        return {
            'dispatched': False,
            'status': 'pending_configuration',
            'correlation_id': bundle['correlation_id'],
            'erro': 'GITHUB_PAT nao configurado no ReqSys',
        }
    encoded = _compactar(bundle)
    if len(encoded) > 60000:
        raise ValueError('Bundle WSJF excede o limite seguro do workflow_dispatch')
    repo = settings.github_alm_repo or DEFAULT_ALM_REPO
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches'
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
            'activate_after_import': 'false',
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
        'workflow_url': f'https://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}',
        'flows': ['ReqSys WSJF - Planner para Excel'],
    }
