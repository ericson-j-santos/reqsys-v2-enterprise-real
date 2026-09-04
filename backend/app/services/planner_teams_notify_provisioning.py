from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

PROFILE = 'planner_teams_notificacao_simples'
FLOW_MANAGEMENT_BASE = 'https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple'
SCHEMA = 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
PLANNER_API = '/providers/Microsoft.PowerApps/apis/shared_planner'

EVENTOS = {
    'criada': {
        'operation_id': 'OnNewTask_V3',
        'trigger_name': 'Quando_uma_tarefa_e_criada',
        'display_name': 'ReqSys - Notificar Teams (Tarefa criada no Planner)',
        'titulo_mensagem': 'Nova tarefa criada no Planner',
    },
    'concluida': {
        'operation_id': 'OnCompleteTask_V3',
        'trigger_name': 'Quando_uma_tarefa_e_concluida',
        'display_name': 'ReqSys - Notificar Teams (Tarefa concluída no Planner)',
        'titulo_mensagem': 'Tarefa concluída no Planner',
    },
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


def _adaptive_card(titulo_mensagem: str) -> dict[str, Any]:
    return {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': '1.2',
        'body': [
            {'type': 'TextBlock', 'size': 'Medium', 'weight': 'Bolder', 'text': titulo_mensagem},
            {
                'type': 'TextBlock',
                'wrap': True,
                'text': "@{triggerBody()?['title']}",
            },
            {
                'type': 'FactSet',
                'facts': [
                    {'title': 'Plano', 'value': "@{parameters('PLANNER_PLAN_ID')}"},
                    {'title': 'Percentual', 'value': "@{string(triggerBody()?['percentComplete'])}%"},
                    {'title': 'Vencimento', 'value': "@{coalesce(triggerBody()?['dueDateTime'], 'sem prazo')}"},
                ],
            },
        ],
    }


def gerar_definicao(payload: dict[str, Any], evento: str) -> dict[str, Any]:
    config = EVENTOS[evento]
    card = _adaptive_card(config['titulo_mensagem'])
    trigger = {
        'type': 'OpenApiConnection',
        'inputs': {
            'host': {
                'apiId': PLANNER_API,
                'operationId': config['operation_id'],
                'connectionName': 'shared_planner',
            },
            'parameters': {
                'group_id': "@parameters('PLANNER_GROUP_ID')",
                'id': "@parameters('PLANNER_PLAN_ID')",
            },
        },
        'splitOn': "@triggerBody()?['value']",
    }
    notificar_teams = {
        'type': 'Http',
        'inputs': {
            'method': 'POST',
            'uri': "@parameters('TEAMS_WEBHOOK_URL')",
            'headers': {'Content-Type': 'application/json'},
            'body': {
                'type': 'message',
                'attachments': [
                    {'contentType': 'application/vnd.microsoft.card.adaptive', 'content': card}
                ],
            },
        },
        'runAfter': {},
    }
    return {
        '$schema': SCHEMA,
        'contentVersion': '1.0.0.0',
        'parameters': {
            '$authentication': {'defaultValue': {}, 'type': 'SecureObject'},
            '$connections': {'defaultValue': {}, 'type': 'Object'},
            'PLANNER_GROUP_ID': {'defaultValue': payload['group_id'], 'type': 'String'},
            'PLANNER_PLAN_ID': {'defaultValue': payload['plan_id'], 'type': 'String'},
            'TEAMS_WEBHOOK_URL': {'defaultValue': payload['teams_webhook_url'], 'type': 'String'},
        },
        'triggers': {config['trigger_name']: trigger},
        'actions': {'Notificar_Teams': notificar_teams},
    }


def validar_definicao(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if definition.get('$schema') != SCHEMA:
        errors.append('schema_invalido')
    if not definition.get('triggers'):
        errors.append('trigger_ausente')
    trigger = next(iter(definition.get('triggers', {}).values()), {})
    host = trigger.get('inputs', {}).get('host', {})
    if host.get('apiId') != PLANNER_API:
        errors.append('trigger_conector_nao_permitido')
    if host.get('operationId') not in {e['operation_id'] for e in EVENTOS.values()}:
        errors.append('trigger_operacao_nao_permitida')
    actions = definition.get('actions', {})
    if 'Notificar_Teams' not in actions:
        errors.append('acao_notificar_teams_ausente')
    elif actions['Notificar_Teams'].get('type') != 'Http':
        errors.append('acao_notificar_teams_tipo_invalido')
    raw = json.dumps(definition, ensure_ascii=False)
    if 'UpdateTask' in raw:
        errors.append('escrita_planner_proibida')
    return errors


def montar_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get('target_environment') or 'dev').strip().lower()
    if target not in {'dev', 'development'}:
        raise ValueError('O perfil planner_teams_notificacao_simples está restrito a DEV neste incremento')
    if not (payload.get('teams_webhook_url') or '').strip():
        raise ValueError('Webhook do Teams nao configurado (TEAMS_NOTIFICATIONS_WEBHOOK_URL)')

    correlation_id = payload.get('correlation_id') or str(uuid.uuid4())
    flows = []
    for evento, config in EVENTOS.items():
        definition = gerar_definicao(payload, evento)
        errors = validar_definicao(definition)
        if errors:
            raise ValueError(f'Definicao invalida ({evento}): {errors}')
        flows.append(
            {
                'id': f'planner_teams_notificar_{evento}',
                'evento': evento,
                'display_name': config['display_name'],
                'state': 'Stopped',
                'definition': definition,
            }
        )
    return {
        'schema_version': '1.0.0',
        'profile': PROFILE,
        'capability': 'Notificar Teams sobre mudancas no Planner',
        'correlation_id': correlation_id,
        'target': {
            'environment_id': payload['environment_id'],
            'environment_url': payload['environment_url'],
            'target_environment': 'dev',
        },
        'connections': {'planner': payload['planner_connection_id']},
        'flows': flows,
    }


async def _buscar_flow_existente(
    client: httpx.AsyncClient, base_url: str, headers: dict[str, str], display_name: str
) -> str | None:
    response = await client.get(base_url, headers=headers, params={'api-version': '2016-11-01'})
    if response.status_code != 200:
        return None
    for item in response.json().get('value', []):
        if item.get('properties', {}).get('displayName') == display_name:
            return item.get('name')
    return None


async def despachar(payload: dict[str, Any], *, user_token: str | None = None) -> dict[str, Any]:
    """Cria/atualiza os fluxos de notificacao Planner->Teams de verdade.

    Mesmo padrao provado em wsjf_planner_excel_provisioning.py: a API de
    gerenciamento de fluxos (api.flow.microsoft.com) nao aceita credencial
    app-only, so token delegado do usuario; nao ha upsert por id escolhido
    pelo cliente (o id e gerado no POST), entao a idempotencia busca por
    displayName a cada execucao e faz PATCH no id real encontrado, ou POST
    para criar quando nao existe.
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
    safe_environment_id = _segmento_id_seguro(payload['environment_id'], 'Ambiente')
    base_url = f'{FLOW_MANAGEMENT_BASE}/environments/{safe_environment_id}/flows'
    headers = {'Authorization': f'Bearer {user_token}'}
    resultados = []
    async with httpx.AsyncClient(timeout=30) as client:
        for flow in bundle['flows']:
            body = {
                'properties': {
                    'displayName': flow['display_name'],
                    'definition': flow['definition'],
                    'connectionReferences': {
                        'shared_planner': {'connectionName': bundle['connections']['planner'], 'id': PLANNER_API},
                    },
                    'state': 'Stopped',
                },
            }
            flow_id = await _buscar_flow_existente(client, base_url, headers, flow['display_name'])
            if flow_id:
                response = await client.patch(
                    f'{base_url}/{flow_id}', headers=headers, params={'api-version': '2016-11-01'}, json=body
                )
            else:
                response = await client.post(base_url, headers=headers, params={'api-version': '2016-11-01'}, json=body)
            if response.status_code not in (200, 201):
                resultados.append(
                    {
                        'evento': flow['evento'],
                        'dispatched': False,
                        'status_code': response.status_code,
                        'erro': response.text[:500],
                    }
                )
                continue
            data = response.json()
            flow_id = data.get('name') or flow_id
            resultados.append(
                {
                    'evento': flow['evento'],
                    'dispatched': True,
                    'flow_id': flow_id,
                    'flow_url': f'https://make.powerautomate.com/environments/{safe_environment_id}/flows/{flow_id}/details',
                }
            )
    todos_ok = all(r['dispatched'] for r in resultados)
    return {
        'dispatched': todos_ok,
        'status': 'implantado' if todos_ok else 'erro_parcial',
        'correlation_id': bundle['correlation_id'],
        'flows': resultados,
    }
