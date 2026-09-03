from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

import httpx

PROFILE = 'wsjf_planner_excel_simples'
FLOW_MANAGEMENT_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
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


def _segmento_id_seguro(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f'{label} obrigatorio')
    parts = normalized.split('-')
    for part in parts:
        if not part or not part.isalnum():
            raise ValueError(f'{label} invalido')
    return '-'.join(parts)


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


async def despachar(payload: dict[str, Any], *, user_token: str | None = None) -> dict[str, Any]:
    """Cria/atualiza o fluxo Planner->Excel de verdade no Power Automate.

    A API de gerenciamento de fluxos (api.flow.microsoft.com) nao aceita
    credencial app-only (client_credentials) — so token delegado do proprio
    usuario. Por isso este provisionamento e feito diretamente pelo backend
    com o token que o frontend adquire via MSAL (mesmo padrao ja usado para
    "Conexoes Microsoft"), em vez de relay via GitHub Actions/PAC CLI.

    flow_guid e deterministico (uuid5 fixo): reexecutar "Instalar fluxo"
    atualiza o mesmo fluxo em vez de criar duplicatas.

    O verbo e PATCH, nao PUT: confirmado em DEV que PUT em
    .../flows/{id} devolve 404 de roteamento ("No HTTP resource was
    found that matches the request URI") mesmo com payload valido —
    essa API (Microsoft.ProcessSimple) so registra rota para
    GET/PATCH/DELETE em .../flows/{id}; criacao e atualizacao usam o
    mesmo PATCH com upsert pelo id informado.
    """
    bundle = montar_bundle(payload)
    if not payload.get('confirmar'):
        return {
            'dispatched': False,
            'status': 'validado_sem_implantar',
            'correlation_id': bundle['correlation_id'],
            'bundle': bundle,
        }
    if not user_token:
        return {
            'dispatched': False,
            'status': 'pending_configuration',
            'correlation_id': bundle['correlation_id'],
            'erro': 'Token delegado do Power Automate ausente: verifique se a permissao delegada Flows.Manage.All foi consentida no Microsoft Entra.',
        }
    flow = bundle['flows'][0]
    safe_environment_id = _segmento_id_seguro(payload['environment_id'], 'Ambiente')
    url = f"{FLOW_MANAGEMENT_BASE}/environments/{safe_environment_id}/flows/{flow['flow_guid']}"
    body = {
        'properties': {
            'displayName': flow['display_name'],
            'definition': flow['definition'],
            'connectionReferences': {
                'shared_planner': {'connectionName': bundle['connections']['planner'], 'id': PLANNER_API},
                'shared_excelonlinebusiness': {'connectionName': bundle['connections']['excel'], 'id': EXCEL_API},
            },
            'state': 'Stopped',
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.patch(
            url,
            headers={'Authorization': f'Bearer {user_token}'},
            params={'api-version': '2016-11-01'},
            json=body,
        )
    if response.status_code not in (200, 201):
        return {
            'dispatched': False,
            'status': 'erro_provisionamento',
            'status_code': response.status_code,
            'erro': response.text[:500],
            'correlation_id': bundle['correlation_id'],
        }
    data = response.json()
    return {
        'dispatched': True,
        'status': 'implantado',
        'correlation_id': bundle['correlation_id'],
        'flow_id': data.get('name') or flow['flow_guid'],
        'flow_url': f"https://make.powerautomate.com/environments/{safe_environment_id}/flows/{flow['flow_guid']}/details",
        'flows': [flow['display_name']],
    }
