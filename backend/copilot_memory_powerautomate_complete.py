from __future__ import annotations

import json
from typing import Any, Iterator

SCHEMA = 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
PLANNER_API = '/providers/Microsoft.PowerApps/apis/shared_planner'
EXCEL_API = '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness'
ALLOWED_APIS = {PLANNER_API, EXCEL_API}


def _parameters() -> dict[str, Any]:
    return {
        '$authentication': {'defaultValue': {}, 'type': 'SecureObject'},
        '$connections': {'defaultValue': {}, 'type': 'Object'},
        'PLANNER_GROUP_ID': {'defaultValue': 'PREENCHER_GROUP_ID', 'type': 'String'},
        'PLANNER_PLAN_ID': {'defaultValue': 'PREENCHER_PLAN_ID', 'type': 'String'},
        'EXCEL_SOURCE': {'defaultValue': 'PREENCHER_SHAREPOINT_SITE_URL_OU_ME', 'type': 'String'},
        'EXCEL_DRIVE': {'defaultValue': 'PREENCHER_DOCUMENT_LIBRARY_ID', 'type': 'String'},
        'EXCEL_FILE': {'defaultValue': 'PREENCHER_ARQUIVO_XLSX_ID_OU_CAMINHO', 'type': 'String'},
    }


def _definition(actions: dict[str, Any], *, minutes: int) -> dict[str, Any]:
    return {
        '$schema': SCHEMA,
        'contentVersion': '1.0.0.0',
        'parameters': _parameters(),
        'triggers': {
            'Recorrencia': {
                'type': 'Recurrence',
                'recurrence': {'frequency': 'Minute', 'interval': minutes},
            }
        },
        'actions': actions,
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


def _excel(
    operation: str,
    parameters: dict[str, Any],
    *,
    run_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _openapi(
        EXCEL_API,
        'shared_excelonlinebusiness',
        operation,
        parameters,
        run_after=run_after,
    )


def _planner(
    operation: str,
    parameters: dict[str, Any],
    *,
    run_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _openapi(
        PLANNER_API,
        'shared_planner',
        operation,
        parameters,
        run_after=run_after,
    )


def _excel_base(table: str) -> dict[str, Any]:
    return {
        'source': "@parameters('EXCEL_SOURCE')",
        'drive': "@parameters('EXCEL_DRIVE')",
        'file': "@parameters('EXCEL_FILE')",
        'table': table,
    }


def _assinatura_tarefa(expr: str) -> str:
    return (
        "@concat(coalesce(" + expr + "?['id'],''),'|',"
        "coalesce(" + expr + "?['title'],''),'|',"
        "string(coalesce(" + expr + "?['percentComplete'],0)),'|',"
        "coalesce(" + expr + "?['dueDateTime'],''))"
    )


def _historico(
    *,
    memory_id: str,
    planner_task_id: str,
    origem: str,
    tipo: str,
    resumo: str,
    signature: str,
    versao: str | int = '',
    run_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _excel(
        'AddRowV2',
        {
            **_excel_base('tbHistoricoCopilot'),
            'item': {
                'EventId': '@guid()',
                'MemoryId': memory_id,
                'PlannerTaskId': planner_task_id,
                'Versao': versao,
                'Origem': origem,
                'TipoEvento': tipo,
                'Resumo': resumo,
                'PlannerSignature': signature,
                'CorrelationId': "@workflow()?['run']?['name']",
                'CriadoEm': '@utcNow()',
            },
        },
        run_after=run_after,
    )


def fluxo_planner_para_excel() -> dict[str, Any]:
    listar = _planner(
        'ListTasks_V3',
        {
            'groupId': "@parameters('PLANNER_GROUP_ID')",
            'id': "@parameters('PLANNER_PLAN_ID')",
        },
    )
    buscar_memoria = _excel(
        'GetItems',
        {
            **_excel_base('tbMemoriaCopilot'),
            '$filter': "@concat('PlannerTaskId eq ''',items('Para_cada_tarefa')?['id'],'''')",
            '$top': 1,
        },
    )
    buscar_comando = _excel(
        'GetItems',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            '$filter': (
                "@concat('PlannerTaskId eq ''',items('Para_cada_tarefa')?['id'],"
                "''' and AtualizarPlanner eq ''SIM''')"
            ),
            '$top': 1,
        },
        run_after={'Buscar_memoria': ['Succeeded']},
    )
    assinatura = {
        'type': 'Compose',
        'inputs': _assinatura_tarefa("items('Para_cada_tarefa')"),
        'runAfter': {'Buscar_comando_pendente': ['Succeeded']},
    }
    criar_memoria = _excel(
        'AddRowV2',
        {
            **_excel_base('tbMemoriaCopilot'),
            'item': {
                'MemoryId': "@concat('planner-',items('Para_cada_tarefa')?['id'])",
                'PlannerTaskId': "@items('Para_cada_tarefa')?['id']",
                'Assunto': "@items('Para_cada_tarefa')?['title']",
                'Contexto': '',
                'EstadoAtual': '',
                'Decisao': '',
                'Pendencia': '',
                'ProximoPasso': '',
                'FonteUrl': '',
                'DataFonte': '',
                'Validade': 'ativa',
                'PlannerTitulo': "@items('Para_cada_tarefa')?['title']",
                'PlannerStatus': (
                    "@if(equals(items('Para_cada_tarefa')?['percentComplete'],100),"
                    "'concluida','ativa')"
                ),
                'PlannerPercentual': "@items('Para_cada_tarefa')?['percentComplete']",
                'PlannerPrazo': "@items('Para_cada_tarefa')?['dueDateTime']",
                'Versao': 1,
                'ContentHash': "@outputs('Assinatura_Planner')",
                'PlannerSyncStatus': 'SINCRONIZADO',
                'PlannerAppliedSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
    )
    historico_criacao = _historico(
        memory_id="@concat('planner-',items('Para_cada_tarefa')?['id'])",
        planner_task_id="@items('Para_cada_tarefa')?['id']",
        origem='planner',
        tipo='CRIADA',
        resumo='Memoria criada a partir do Planner',
        signature="@outputs('Assinatura_Planner')",
        versao=1,
        run_after={'Criar_memoria': ['Succeeded']},
    )
    marcar_conflito = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@first(body('Buscar_memoria')?['value'])?['MemoryId']",
            'item': {
                'PlannerSyncStatus': 'CONFLITO',
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
    )
    historico_conflito = _historico(
        memory_id="@first(body('Buscar_memoria')?['value'])?['MemoryId']",
        planner_task_id="@items('Para_cada_tarefa')?['id']",
        origem='planner',
        tipo='CONFLITO',
        resumo='Planner mudou enquanto existia comando pendente; memoria preservada',
        signature="@outputs('Assinatura_Planner')",
        versao="@first(body('Buscar_memoria')?['value'])?['Versao']",
        run_after={'Marcar_conflito': ['Succeeded']},
    )
    atualizar_memoria = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@first(body('Buscar_memoria')?['value'])?['MemoryId']",
            'item': {
                'PlannerTitulo': "@items('Para_cada_tarefa')?['title']",
                'PlannerStatus': (
                    "@if(equals(items('Para_cada_tarefa')?['percentComplete'],100),"
                    "'concluida','ativa')"
                ),
                'PlannerPercentual': "@items('Para_cada_tarefa')?['percentComplete']",
                'PlannerPrazo': "@items('Para_cada_tarefa')?['dueDateTime']",
                'Versao': (
                    "@add(int(coalesce(first(body('Buscar_memoria')?['value'])?['Versao'],0)),1)"
                ),
                'ContentHash': "@outputs('Assinatura_Planner')",
                'PlannerSyncStatus': 'SINCRONIZADO',
                'PlannerAppliedSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
    )
    historico_atualizacao = _historico(
        memory_id="@first(body('Buscar_memoria')?['value'])?['MemoryId']",
        planner_task_id="@items('Para_cada_tarefa')?['id']",
        origem='planner',
        tipo='ATUALIZADA',
        resumo='Estado operacional atualizado a partir do Planner',
        signature="@outputs('Assinatura_Planner')",
        versao=(
            "@add(int(coalesce(first(body('Buscar_memoria')?['value'])?['Versao'],0)),1)"
        ),
        run_after={'Atualizar_memoria': ['Succeeded']},
    )
    mudou = {
        'type': 'If',
        'expression': (
            "@not(equals(first(body('Buscar_memoria')?['value'])?"
            "['PlannerAppliedSignature'],outputs('Assinatura_Planner')))"
        ),
        'actions': {
            'Existe_comando_pendente': {
                'type': 'If',
                'expression': "@not(empty(body('Buscar_comando_pendente')?['value']))",
                'actions': {
                    'Marcar_conflito': marcar_conflito,
                    'Historico_conflito': historico_conflito,
                },
                'else': {
                    'actions': {
                        'Atualizar_memoria': atualizar_memoria,
                        'Historico_atualizacao': historico_atualizacao,
                    }
                },
                'runAfter': {},
            }
        },
        'else': {'actions': {}},
        'runAfter': {},
    }
    criar_ou_atualizar = {
        'type': 'If',
        'expression': "@empty(body('Buscar_memoria')?['value'])",
        'actions': {
            'Criar_memoria': criar_memoria,
            'Historico_criacao': historico_criacao,
        },
        'else': {'actions': {'Se_estado_mudou': mudou}},
        'runAfter': {'Assinatura_Planner': ['Succeeded']},
    }
    foreach = {
        'type': 'Foreach',
        'foreach': "@body('Listar_tarefas')?['value']",
        'actions': {
            'Buscar_memoria': buscar_memoria,
            'Buscar_comando_pendente': buscar_comando,
            'Assinatura_Planner': assinatura,
            'Criar_ou_atualizar': criar_ou_atualizar,
        },
        'runAfter': {'Listar_tarefas': ['Succeeded']},
    }
    return _definition(
        {'Listar_tarefas': listar, 'Para_cada_tarefa': foreach},
        minutes=15,
    )


def fluxo_excel_para_planner() -> dict[str, Any]:
    listar_comandos = _excel(
        'GetItems',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            '$filter': "AtualizarPlanner eq 'SIM'",
        },
    )
    buscar_memoria = _excel(
        'GetItems',
        {
            **_excel_base('tbMemoriaCopilot'),
            '$filter': (
                "@concat('MemoryId eq ''',items('Para_cada_comando')?['MemoryId'],'''')"
            ),
            '$top': 1,
        },
    )
    reler_tarefa = _planner(
        'GetTask_V2',
        {'id': "@items('Para_cada_comando')?['PlannerTaskId']"},
        run_after={'Buscar_memoria': ['Succeeded']},
    )
    assinatura_atual = {
        'type': 'Compose',
        'inputs': _assinatura_tarefa("body('Reler_tarefa')"),
        'runAfter': {'Reler_tarefa': ['Succeeded']},
    }
    assinatura_desejada = {
        'type': 'Compose',
        'inputs': (
            "@concat(coalesce(items('Para_cada_comando')?['PlannerTaskId'],''),'|',"
            "coalesce(items('Para_cada_comando')?['PlannerTitulo'],''),'|',"
            "string(coalesce(items('Para_cada_comando')?['PlannerPercentual'],0)),'|',"
            "coalesce(items('Para_cada_comando')?['PlannerPrazo'],''))"
        ),
        'runAfter': {'Assinatura_atual': ['Succeeded']},
    }
    comando_erro_memoria = _excel(
        'PatchItem',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'ResultadoSync': 'ERRO',
                'DetalheConflito': 'MemoryId nao encontrado em tbMemoriaCopilot.',
                'CorrelationId': "@workflow()?['run']?['name']",
            },
        },
    )
    comando_conflito = _excel(
        'PatchItem',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'ResultadoSync': 'CONFLITO',
                'DetalheConflito': (
                    'Planner mudou desde a ultima memoria confirmada; nenhuma escrita foi aplicada.'
                ),
                'CorrelationId': "@workflow()?['run']?['name']",
            },
        },
    )
    memoria_conflito = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'PlannerSyncStatus': 'CONFLITO',
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
        run_after={'Marcar_comando_conflito': ['Succeeded']},
    )
    historico_conflito = _historico(
        memory_id="@items('Para_cada_comando')?['MemoryId']",
        planner_task_id="@items('Para_cada_comando')?['PlannerTaskId']",
        origem='excel',
        tipo='CONFLITO',
        resumo='Alteracao Excel bloqueada porque Planner mudou',
        signature="@outputs('Assinatura_atual')",
        run_after={'Marcar_memoria_conflito': ['Succeeded']},
    )
    marcar_pendente = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'PlannerSyncStatus': 'PENDENTE',
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
    )
    atualizar_planner = _planner(
        'UpdateTask_V2',
        {
            'id': "@items('Para_cada_comando')?['PlannerTaskId']",
            'title': "@items('Para_cada_comando')?['PlannerTitulo']",
            'percentComplete': (
                "@string(int(coalesce(items('Para_cada_comando')?['PlannerPercentual'],0)))"
            ),
            'dueDateTime': (
                "@if(empty(items('Para_cada_comando')?['PlannerPrazo']),"
                "null,items('Para_cada_comando')?['PlannerPrazo'])"
            ),
        },
        run_after={'Marcar_memoria_pendente': ['Succeeded']},
    )
    finalizar_comando = _excel(
        'PatchItem',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'AtualizarPlanner': 'NAO',
                'ResultadoSync': 'SINCRONIZADO',
                'DetalheConflito': '',
                'CorrelationId': "@workflow()?['run']?['name']",
            },
        },
        run_after={'Atualizar_Planner': ['Succeeded']},
    )
    finalizar_memoria = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'PlannerTitulo': "@items('Para_cada_comando')?['PlannerTitulo']",
                'PlannerPercentual': "@items('Para_cada_comando')?['PlannerPercentual']",
                'PlannerPrazo': "@items('Para_cada_comando')?['PlannerPrazo']",
                'PlannerSyncStatus': 'SINCRONIZADO',
                'PlannerAppliedSignature': "@outputs('Assinatura_desejada')",
                'ContentHash': "@outputs('Assinatura_desejada')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
        run_after={'Finalizar_comando': ['Succeeded']},
    )
    historico_sucesso = _historico(
        memory_id="@items('Para_cada_comando')?['MemoryId']",
        planner_task_id="@items('Para_cada_comando')?['PlannerTaskId']",
        origem='excel',
        tipo='PLANNER_ATUALIZADO',
        resumo='Alteracao autorizada aplicada ao Planner',
        signature="@outputs('Assinatura_desejada')",
        run_after={'Finalizar_memoria': ['Succeeded']},
    )
    memoria_erro = _excel(
        'PatchItem',
        {
            **_excel_base('tbMemoriaCopilot'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'PlannerSyncStatus': 'ERRO',
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
        run_after={'Atualizar_Planner': ['Failed', 'TimedOut']},
    )
    comando_erro = _excel(
        'PatchItem',
        {
            **_excel_base('tbAtualizacoesPlanner'),
            'idColumn': 'MemoryId',
            'id': "@items('Para_cada_comando')?['MemoryId']",
            'item': {
                'ResultadoSync': 'ERRO',
                'DetalheConflito': 'Falha ao atualizar Planner; comando mantido para nova tentativa.',
                'CorrelationId': "@workflow()?['run']?['name']",
            },
        },
        run_after={'Marcar_memoria_erro': ['Succeeded']},
    )
    sem_conflito = {
        'type': 'If',
        'expression': (
            "@equals(outputs('Assinatura_atual'),"
            "first(body('Buscar_memoria')?['value'])?['PlannerAppliedSignature'])"
        ),
        'actions': {
            'Marcar_memoria_pendente': marcar_pendente,
            'Atualizar_Planner': atualizar_planner,
            'Finalizar_comando': finalizar_comando,
            'Finalizar_memoria': finalizar_memoria,
            'Historico_sucesso': historico_sucesso,
            'Marcar_memoria_erro': memoria_erro,
            'Marcar_comando_erro': comando_erro,
        },
        'else': {
            'actions': {
                'Marcar_comando_conflito': comando_conflito,
                'Marcar_memoria_conflito': memoria_conflito,
                'Historico_conflito': historico_conflito,
            }
        },
        'runAfter': {'Assinatura_desejada': ['Succeeded']},
    }
    memoria_existe = {
        'type': 'If',
        'expression': "@not(empty(body('Buscar_memoria')?['value']))",
        'actions': {'Aplicar_somente_sem_conflito': sem_conflito},
        'else': {'actions': {'Marcar_comando_erro_memoria': comando_erro_memoria}},
        'runAfter': {'Assinatura_desejada': ['Succeeded']},
    }
    foreach = {
        'type': 'Foreach',
        'foreach': "@body('Listar_comandos')?['value']",
        'actions': {
            'Buscar_memoria': buscar_memoria,
            'Reler_tarefa': reler_tarefa,
            'Assinatura_atual': assinatura_atual,
            'Assinatura_desejada': assinatura_desejada,
            'Validar_memoria': memoria_existe,
        },
        'runAfter': {'Listar_comandos': ['Succeeded']},
    }
    return _definition(
        {'Listar_comandos': listar_comandos, 'Para_cada_comando': foreach},
        minutes=15,
    )


def fluxo_saude() -> dict[str, Any]:
    listar_memoria = _excel('GetItems', {**_excel_base('tbMemoriaCopilot')})
    filtrar = {
        'type': 'Query',
        'inputs': {
            'from': "@body('Listar_memoria')?['value']",
            'where': (
                "@or(equals(toUpper(coalesce(item()?['PlannerSyncStatus'],'')),'CONFLITO'),"
                "equals(toUpper(coalesce(item()?['PlannerSyncStatus'],'')),'ERRO'))"
            ),
        },
        'runAfter': {'Listar_memoria': ['Succeeded']},
    }
    validar = {
        'type': 'If',
        'expression': "@greater(length(body('Filtrar_problemas')),0)",
        'actions': {
            'Falhar_visivelmente': {
                'type': 'Terminate',
                'inputs': {
                    'runStatus': 'Failed',
                    'runError': {
                        'code': 'COPILOT_MEMORY_HEALTH',
                        'message': (
                            "@concat('Conflitos/erros encontrados: ',"
                            "string(length(body('Filtrar_problemas'))))"
                        ),
                    },
                },
                'runAfter': {},
            }
        },
        'else': {
            'actions': {
                'Saude_OK': {'type': 'Compose', 'inputs': 'OK', 'runAfter': {}}
            }
        },
        'runAfter': {'Filtrar_problemas': ['Succeeded']},
    }
    return _definition(
        {
            'Listar_memoria': listar_memoria,
            'Filtrar_problemas': filtrar,
            'Validar_saude': validar,
        },
        minutes=60,
    )


def connection_references_template() -> dict[str, Any]:
    return {
        'shared_planner': {
            'connectionName': 'PREENCHER_CONNECTION_NAME_PLANNER',
            'source': 'Embedded',
            'id': PLANNER_API,
        },
        'shared_excelonlinebusiness': {
            'connectionName': 'PREENCHER_CONNECTION_NAME_EXCEL',
            'source': 'Embedded',
            'id': EXCEL_API,
        },
    }


def gerar_fluxos_completos() -> list[dict[str, Any]]:
    return [
        {
            'id': '01_planner_para_excel',
            'display_name': 'Copilot Memory - Planner para Excel',
            'state': 'Stopped',
            'definition': fluxo_planner_para_excel(),
        },
        {
            'id': '02_excel_para_planner',
            'display_name': 'Copilot Memory - Excel para Planner',
            'state': 'Stopped',
            'definition': fluxo_excel_para_planner(),
        },
        {
            'id': '03_saude',
            'display_name': 'Copilot Memory - Saude',
            'state': 'Stopped',
            'definition': fluxo_saude(),
        },
    ]


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
    parameters = definition.get('parameters', {})
    for required in ('$authentication', '$connections'):
        if required not in parameters:
            errors.append(f'parametro_ausente:{required}')
    if not definition.get('triggers'):
        errors.append('gatilho_ausente')
    if not definition.get('actions'):
        errors.append('acoes_ausentes')
    raw = json.dumps(definition, ensure_ascii=False).lower()
    if 'shared_commondataserviceforapps' in raw:
        errors.append('dataverse_proibido_no_perfil_restrito')
    if 'updatetask_v3' in raw:
        errors.append('planner_preview_proibido')
    for action_name, action in _walk_actions(definition.get('actions', {})):
        if action.get('type') != 'OpenApiConnection':
            continue
        host = action.get('inputs', {}).get('host', {})
        if host.get('apiId') not in ALLOWED_APIS:
            errors.append(f'conector_nao_permitido:{action_name}')
        if not host.get('operationId'):
            errors.append(f'operation_id_ausente:{action_name}')
    return errors


def deployment_index() -> dict[str, Any]:
    flows = gerar_fluxos_completos()
    return {
        'version': '1.1.0',
        'mode': 'power_automate_complete_definitions',
        'flows': [
            {
                'id': flow['id'],
                'displayName': flow['display_name'],
                'definitionFile': f"powerautomate/definitions/{flow['id']}.json",
                'connectionReferencesFile': 'powerautomate/connection-references.json',
                'initialState': flow['state'],
            }
            for flow in flows
        ],
        'requiredConnections': ['shared_planner', 'shared_excelonlinebusiness'],
        'manualBoundary': (
            'autenticar Planner e Excel Online Business no tenant e informar os IDs do ambiente; '
            'a logica dos tres fluxos ja esta completa'
        ),
    }
