from __future__ import annotations

import json
from typing import Any

SCHEMA = 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
PLANNER_API = '/providers/Microsoft.PowerApps/apis/shared_planner'
EXCEL_API = '/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness'


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


def _excel(operation: str, parameters: dict[str, Any], *, run_after: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'type': 'OpenApiConnection',
        'inputs': {
            'parameters': parameters,
            'host': {
                'apiId': EXCEL_API,
                'operationId': operation,
                'connectionName': 'shared_excelonlinebusiness',
            },
        },
        'runAfter': run_after or {},
    }


def _planner(operation: str, parameters: dict[str, Any], *, run_after: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'type': 'OpenApiConnection',
        'inputs': {
            'parameters': parameters,
            'host': {
                'apiId': PLANNER_API,
                'operationId': operation,
                'connectionName': 'shared_planner',
            },
        },
        'runAfter': run_after or {},
    }


def _excel_base(table: str) -> dict[str, Any]:
    return {
        'source': "@parameters('EXCEL_SOURCE')",
        'drive': "@parameters('EXCEL_DRIVE')",
        'file': "@parameters('EXCEL_FILE')",
        'table': table,
    }


def _assinatura_tarefa(expr: str) -> str:
    return (
        "@concat(coalesce(" + expr + "?['id'],''),'|',coalesce(" + expr + "?['title'],''),'|',"
        "string(coalesce(" + expr + "?['percentComplete'],0)),'|',coalesce(" + expr + "?['dueDateTime'],''))"
    )


def fluxo_planner_para_excel() -> dict[str, Any]:
    listar = _planner(
        'ListTasks_V3',
        {'groupId': "@parameters('PLANNER_GROUP_ID')", 'id': "@parameters('PLANNER_PLAN_ID')"},
    )
    buscar_memoria = _excel(
        'GetItems',
        {
            **_excel_base('tbMemoriaCopilot'),
            '$filter': "@concat('PlannerTaskId eq ''', items('Para_cada_tarefa')?['id'], '''')",
            '$top': 1,
        },
    )
    assinatura = {
        'type': 'Compose',
        'inputs': _assinatura_tarefa("items('Para_cada_tarefa')"),
        'runAfter': {'Buscar_memoria': ['Succeeded']},
    }
    add_memory = _excel(
        'AddRowV2',
        {
            **_excel_base('tbMemoriaCopilot'),
            'item': {
                'MemoryId': "@concat('planner-',items('Para_cada_tarefa')?['id'])",
                'PlannerTaskId': "@items('Para_cada_tarefa')?['id']",
                'Assunto': "@items('Para_cada_tarefa')?['title']",
                'Contexto': '', 'EstadoAtual': '', 'Decisao': '', 'Pendencia': '', 'ProximoPasso': '',
                'FonteUrl': '', 'DataFonte': '', 'Validade': 'ativa',
                'PlannerTitulo': "@items('Para_cada_tarefa')?['title']",
                'PlannerStatus': "@if(equals(items('Para_cada_tarefa')?['percentComplete'],100),'concluida','ativa')",
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
    add_history_new = _excel(
        'AddRowV2',
        {
            **_excel_base('tbHistoricoCopilot'),
            'item': {
                'EventId': "@guid()",
                'MemoryId': "@concat('planner-',items('Para_cada_tarefa')?['id'])",
                'PlannerTaskId': "@items('Para_cada_tarefa')?['id']",
                'Versao': 1,
                'Origem': 'planner',
                'TipoEvento': 'CRIADA',
                'Resumo': 'Memoria criada a partir do Planner',
                'PlannerSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'CriadoEm': '@utcNow()',
            },
        },
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
    hist_conflito = _excel(
        'AddRowV2',
        {
            **_excel_base('tbHistoricoCopilot'),
            'item': {
                'EventId': '@guid()',
                'MemoryId': "@first(body('Buscar_memoria')?['value'])?['MemoryId']",
                'PlannerTaskId': "@items('Para_cada_tarefa')?['id']",
                'Versao': "@first(body('Buscar_memoria')?['value'])?['Versao']",
                'Origem': 'planner',
                'TipoEvento': 'CONFLITO',
                'Resumo': 'Planner mudou enquanto existia comando pendente',
                'PlannerSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'CriadoEm': '@utcNow()',
            },
        },
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
                'PlannerStatus': "@if(equals(items('Para_cada_tarefa')?['percentComplete'],100),'concluida','ativa')",
                'PlannerPercentual': "@items('Para_cada_tarefa')?['percentComplete']",
                'PlannerPrazo': "@items('Para_cada_tarefa')?['dueDateTime']",
                'Versao': "@add(int(coalesce(first(body('Buscar_memoria')?['value'])?['Versao'],0)),1)",
                'ContentHash': "@outputs('Assinatura_Planner')",
                'PlannerSyncStatus': 'SINCRONIZADO',
                'PlannerAppliedSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'AtualizadoEm': '@utcNow()',
            },
        },
    )
    hist_update = _excel(
        'AddRowV2',
        {
            **_excel_base('tbHistoricoCopilot'),
            'item': {
                'EventId': '@guid()',
                'MemoryId': "@first(body('Buscar_memoria')?['value'])?['MemoryId']",
                'PlannerTaskId': "@items('Para_cada_tarefa')?['id']",
                'Versao': "@add(int(coalesce(first(body('Buscar_memoria')?['value'])?['Versao'],0)),1)",
                'Origem': 'planner',
                'TipoEvento': 'ATUALIZADA',
                'Resumo': 'Estado operacional atualizado a partir do Planner',
                'PlannerSignature': "@outputs('Assinatura_Planner')",
                'CorrelationId': "@workflow()?['run']?['name']",
                'CriadoEm': '@utcNow()',
            },
        },
        run_after={'Atualizar_memoria': ['Succeeded']},
    )
    change_condition = {
        'type': 'If',
        'expression': "@not(equals(first(body('Buscar_memoria')?['value'])?['PlannerAppliedSignature'],outputs('Assinatura_Planner')))",
        'actions': {
            'Detectar_comando_pendente': {
                'type': 'If',
                'expression': "@equals(toUpper(coalesce(first(body('Buscar_memoria')?['value'])?['PlannerSyncStatus'],'')),'PENDENTE')",
                'actions': {'Marcar_conflito': marcar_conflito, 'Historico_conflito': hist_conflito},
                'else': {'actions': {'Atualizar_memoria': atualizar_memoria, 'Historico_atualizacao': hist_update}},
                'runAfter': {},
            }
        },
        'else': {'actions': {}},
        'runAfter': {},
    }
    exists_condition = {
        'type': 'If',
        'expression': "@empty(body('Buscar_memoria')?['value'])",
        'actions': {'Criar_memoria': add_memory, 'Historico_criacao': add_history_new},
        'else': {'actions': {'Se_mudou': change_condition}},
        'runAfter': {'Assinatura_Planner': ['Succeeded']},
    }
    foreach = {
        'type': 'Foreach',
        'foreach': "@body('Listar_tarefas')?['value']",
        'actions': {
            'Buscar_memoria': buscar_memoria,
            'Assinatura_Planner': assinatura,
            'Criar_ou_atualizar': exists_condition,
        },
        'runAfter': {'Listar_tarefas': ['Succeeded']},
    }
    return _definition({'Listar_tarefas': listar, 'Para_cada_tarefa': foreach}, minutes=15)


def fluxo_excel_para_planner() -> dict[str, Any]:
    list_commands = _excel('GetItems', {**_excel_base('tbAtualizacoesPlanner'), '$filter': "AtualizarPlanner eq 'SIM'"})
    get_task = _planner('GetTask_V2', {'id': "@items('Para_cada_comando')?['PlannerTaskId']"})
    current_signature = {'type': 'Compose', 'inputs': _assinatura_tarefa("body('Reler_tarefa')"), 'runAfter': {'Reler_tarefa': ['Succeeded']}}
    desired_signature = {
        'type': 'Compose',
        'inputs': "@concat(coalesce(items('Para_cada_comando')?['PlannerTaskId'],''),'|',coalesce(items('Para_cada_comando')?['PlannerTitulo'],''),'|',string(coalesce(items('Para_cada_comando')?['PlannerPercentual'],0)),'|',coalesce(items('Para_cada_comando')?['PlannerPrazo'],''))",
        'runAfter': {'Assinatura_atual': ['Succeeded']},
    }
    conflict_command = _excel(
        'PatchItem',
        {**_excel_base('tbAtualizacoesPlanner'), 'idColumn': 'MemoryId', 'id': "@items('Para_cada_comando')?['MemoryId']", 'item': {'ResultadoSync': 'CONFLITO', 'DetalheConflito': 'Planner mudou desde a ultima leitura; nenhuma escrita foi aplicada.', 'CorrelationId': "@workflow()?['run']?['name']"}},
    )
    conflict_memory = _excel(
        'PatchItem',
        {**_excel_base('tbMemoriaCopilot'), 'idColumn': 'MemoryId', 'id': "@items('Para_cada_comando')?['MemoryId']", 'item': {'PlannerSyncStatus': 'CONFLITO', 'CorrelationId': "@workflow()?['run']?['name']", 'AtualizadoEm': '@utcNow()'}},
        run_after={'Marcar_comando_conflito': ['Succeeded']},
    )
    conflict_history = _excel(
        'AddRowV2',
        {**_excel_base('tbHistoricoCopilot'), 'item': {'EventId': '@guid()', 'MemoryId': "@items('Para_cada_comando')?['MemoryId']", 'PlannerTaskId': "@items('Para_cada_comando')?['PlannerTaskId']", 'Versao': '', 'Origem': 'excel', 'TipoEvento': 'CONFLITO', 'Resumo': 'Alteracao Excel bloqueada porque Planner mudou', 'PlannerSignature': "@outputs('Assinatura_atual')", 'CorrelationId': "@workflow()?['run']?['name']", 'CriadoEm': '@utcNow()'}},
        run_after={'Marcar_memoria_conflito': ['Succeeded']},
    )
    update_task = _planner(
        'UpdateTask_V3',
        {'id': "@items('Para_cada_comando')?['PlannerTaskId']", 'title': "@items('Para_cada_comando')?['PlannerTitulo']", 'percentComplete': "@int(coalesce(items('Para_cada_comando')?['PlannerPercentual'],0))", 'dueDateTime': "@if(empty(items('Para_cada_comando')?['PlannerPrazo']),null,items('Para_cada_comando')?['PlannerPrazo'])"},
    )
    finish_command = _excel(
        'PatchItem',
        {**_excel_base('tbAtualizacoesPlanner'), 'idColumn': 'MemoryId', 'id': "@items('Para_cada_comando')?['MemoryId']", 'item': {'AtualizarPlanner': 'NAO', 'ResultadoSync': 'SINCRONIZADO', 'DetalheConflito': '', 'CorrelationId': "@workflow()?['run']?['name']"}},
        run_after={'Atualizar_Planner': ['Succeeded']},
    )
    finish_memory = _excel(
        'PatchItem',
        {**_excel_base('tbMemoriaCopilot'), 'idColumn': 'MemoryId', 'id': "@items('Para_cada_comando')?['MemoryId']", 'item': {'PlannerTitulo': "@items('Para_cada_comando')?['PlannerTitulo']", 'PlannerPercentual': "@items('Para_cada_comando')?['PlannerPercentual']", 'PlannerPrazo': "@items('Para_cada_comando')?['PlannerPrazo']", 'PlannerSyncStatus': 'SINCRONIZADO', 'PlannerAppliedSignature': "@outputs('Assinatura_desejada')", 'ContentHash': "@outputs('Assinatura_desejada')", 'CorrelationId': "@workflow()?['run']?['name']", 'AtualizadoEm': '@utcNow()'}},
        run_after={'Finalizar_comando': ['Succeeded']},
    )
    finish_history = _excel(
        'AddRowV2',
        {**_excel_base('tbHistoricoCopilot'), 'item': {'EventId': '@guid()', 'MemoryId': "@items('Para_cada_comando')?['MemoryId']", 'PlannerTaskId': "@items('Para_cada_comando')?['PlannerTaskId']", 'Versao': '', 'Origem': 'excel', 'TipoEvento': 'PLANNER_ATUALIZADO', 'Resumo': 'Alteracao autorizada aplicada ao Planner', 'PlannerSignature': "@outputs('Assinatura_desejada')", 'CorrelationId': "@workflow()?['run']?['name']", 'CriadoEm': '@utcNow()'}},
        run_after={'Atualizar_memoria': ['Succeeded']},
    )
    decision = {
        'type': 'If',
        'expression': "@not(equals(outputs('Assinatura_atual'),coalesce(items('Para_cada_comando')?['PlannerAppliedSignature'],outputs('Assinatura_atual'))))",
        'actions': {'Marcar_comando_conflito': conflict_command, 'Marcar_memoria_conflito': conflict_memory, 'Historico_conflito': conflict_history},
        'else': {'actions': {'Atualizar_Planner': update_task, 'Finalizar_comando': finish_command, 'Atualizar_memoria': finish_memory, 'Historico_sucesso': finish_history}},
        'runAfter': {'Assinatura_desejada': ['Succeeded']},
    }
    foreach = {
        'type': 'Foreach',
        'foreach': "@body('Listar_comandos')?['value']",
        'actions': {'Reler_tarefa': get_task, 'Assinatura_atual': current_signature, 'Assinatura_desejada': desired_signature, 'Aplicar_somente_sem_conflito': decision},
        'runAfter': {'Listar_comandos': ['Succeeded']},
    }
    return _definition({'Listar_comandos': list_commands, 'Para_cada_comando': foreach}, minutes=15)


def fluxo_saude() -> dict[str, Any]:
    list_memory = _excel('GetItems', {**_excel_base('tbMemoriaCopilot')})
    filter_errors = {
        'type': 'Query',
        'inputs': {'from': "@body('Listar_memoria')?['value']", 'where': "@or(equals(toUpper(coalesce(item()?['PlannerSyncStatus'],'')),'CONFLITO'),equals(toUpper(coalesce(item()?['PlannerSyncStatus'],'')),'ERRO'))"},
        'runAfter': {'Listar_memoria': ['Succeeded']},
    }
    decision = {
        'type': 'If',
        'expression': "@greater(length(body('Filtrar_problemas')),0)",
        'actions': {'Falhar_visivelmente': {'type': 'Terminate', 'inputs': {'runStatus': 'Failed', 'runError': {'code': 'COPILOT_MEMORY_HEALTH', 'message': "@concat('Conflitos/erros encontrados: ',string(length(body('Filtrar_problemas'))))"}}, 'runAfter': {}}},
        'else': {'actions': {'Saude_OK': {'type': 'Compose', 'inputs': 'OK', 'runAfter': {}}}},
        'runAfter': {'Filtrar_problemas': ['Succeeded']},
    }
    return _definition({'Listar_memoria': list_memory, 'Filtrar_problemas': filter_errors, 'Validar_saude': decision}, minutes=60)


def connection_references_template() -> dict[str, Any]:
    return {
        'shared_planner': {'connectionName': 'PREENCHER_CONNECTION_NAME_PLANNER', 'source': 'Embedded', 'id': PLANNER_API},
        'shared_excelonlinebusiness': {'connectionName': 'PREENCHER_CONNECTION_NAME_EXCEL', 'source': 'Embedded', 'id': EXCEL_API},
    }


def gerar_fluxos_completos() -> list[dict[str, Any]]:
    return [
        {'id': '01_planner_para_excel', 'display_name': 'Copilot Memory - Planner para Excel', 'state': 'Stopped', 'definition': fluxo_planner_para_excel()},
        {'id': '02_excel_para_planner', 'display_name': 'Copilot Memory - Excel para Planner', 'state': 'Stopped', 'definition': fluxo_excel_para_planner()},
        {'id': '03_saude', 'display_name': 'Copilot Memory - Saude', 'state': 'Stopped', 'definition': fluxo_saude()},
    ]


def _walk_actions(actions: dict[str, Any]):
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
    for action_name, action in _walk_actions(definition.get('actions', {})):
        if action.get('type') == 'OpenApiConnection':
            host = action.get('inputs', {}).get('host', {})
            if host.get('apiId') not in {PLANNER_API, EXCEL_API}:
                errors.append(f'conector_nao_permitido:{action_name}')
            if not host.get('operationId'):
                errors.append(f'operation_id_ausente:{action_name}')
    return errors


def deployment_index() -> dict[str, Any]:
    flows = gerar_fluxos_completos()
    return {
        'version': '1.0.0',
        'mode': 'power_automate_complete_definitions',
        'flows': [
            {'id': flow['id'], 'displayName': flow['display_name'], 'definitionFile': f"powerautomate/definitions/{flow['id']}.json", 'connectionReferencesFile': 'powerautomate/connection-references.json', 'initialState': flow['state']}
            for flow in flows
        ],
        'requiredConnections': ['shared_planner', 'shared_excelonlinebusiness'],
        'manualBoundary': 'autenticar as duas conexoes no tenant e informar ambiente/ids; a logica dos fluxos ja esta completa',
    }
