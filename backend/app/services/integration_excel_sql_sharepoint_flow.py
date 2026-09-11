from __future__ import annotations

from typing import Any, Iterator

SCHEMA = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
EXCEL_API = "/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness"
SQL_API = "/providers/Microsoft.PowerApps/apis/shared_sql"
SHAREPOINT_API = "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"


def _required(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} obrigatório")
    return value


def _openapi(
    api_id: str,
    connection_name: str,
    operation_id: str,
    parameters: dict[str, Any],
    *,
    run_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "OpenApiConnection",
        "inputs": {
            "parameters": parameters,
            "host": {
                "apiId": api_id,
                "operationId": operation_id,
                "connectionName": connection_name,
            },
        },
        "runAfter": run_after or {},
    }


def _walk_actions(actions: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for name, action in actions.items():
        yield name, action
        nested = action.get("actions")
        if isinstance(nested, dict):
            yield from _walk_actions(nested)
        else_actions = action.get("else", {}).get("actions")
        if isinstance(else_actions, dict):
            yield from _walk_actions(else_actions)


def gerar_definicao(payload: dict[str, Any]) -> dict[str, Any]:
    """Gera a definição DEV real do perfil Excel -> SQL Server -> SharePoint."""

    target = str(payload.get("target_environment") or "dev").strip().lower()
    if target not in {"dev", "development"}:
        raise ValueError("A definição E2E está restrita a DEV")

    excel_source = _required(payload, "excel_source")
    excel_drive = _required(payload, "excel_drive")
    excel_file = _required(payload, "excel_file")
    excel_table = str(payload.get("excel_table") or "tbEntrada").strip()
    sql_procedure = _required(payload, "sql_procedure")
    sharepoint_site = _required(payload, "sharepoint_site")
    sharepoint_list = _required(payload, "sharepoint_list")
    correlation_id = _required(payload, "correlation_id")

    row_value = "string(items('Para_cada_linha')?['Identificador'])"
    normalized = f"trim({row_value})"
    valid_expression = (
        "@and("
        f"not(empty({row_value})),"
        f"equals({row_value},{normalized}),"
        f"isInt({row_value}),"
        f"not(startsWith({row_value},'-')),"
        f"not(startsWith({row_value},'+'))"
        ")"
    )

    listar_linhas = _openapi(
        EXCEL_API,
        "shared_excelonlinebusiness",
        "GetItems",
        {
            "source": excel_source,
            "drive": excel_drive,
            "file": excel_file,
            "table": excel_table,
            "$select": "Identificador",
        },
    )

    executar_sql = _openapi(
        SQL_API,
        "shared_sql",
        "ExecuteProcedure_V2",
        {
            "server": "default",
            "database": "default",
            "procedure": sql_procedure,
            "parameters/IdsJson": "@concat('[\"', string(items('Para_cada_linha')?['Identificador']), '\"]')",
            "parameters/CorrelationId": "@parameters('CORRELATION_ID')",
        },
    )

    buscar_sharepoint = _openapi(
        SHAREPOINT_API,
        "shared_sharepointonline",
        "GetItems",
        {
            "dataset": sharepoint_site,
            "table": sharepoint_list,
            "$filter": (
                "@concat('ChaveIntegracao eq ', decodeUriComponent('%27'), "
                "string(items('Para_cada_resultado')?['Identificador']), "
                "decodeUriComponent('%27'))"
            ),
            "$top": 2,
        },
    )

    item = {
        "Title": "@concat('ReqSys ', string(items('Para_cada_resultado')?['Identificador']))",
        "ChaveIntegracao": "@string(items('Para_cada_resultado')?['Identificador'])",
        "CorrelationId": "@parameters('CORRELATION_ID')",
    }

    criar = _openapi(
        SHAREPOINT_API,
        "shared_sharepointonline",
        "PostItem",
        {
            "dataset": sharepoint_site,
            "table": sharepoint_list,
            "item": item,
        },
    )
    atualizar = _openapi(
        SHAREPOINT_API,
        "shared_sharepointonline",
        "PatchItem",
        {
            "dataset": sharepoint_site,
            "table": sharepoint_list,
            "id": "@first(body('Buscar_no_SharePoint')?['value'])?['ID']",
            "item": item,
        },
    )

    upsert = {
        "type": "If",
        "expression": "@empty(body('Buscar_no_SharePoint')?['value'])",
        "actions": {"Criar_item": criar},
        "else": {"actions": {"Atualizar_item": atualizar}},
        "runAfter": {"Buscar_no_SharePoint": ["Succeeded"]},
    }

    resultados = {
        "type": "Foreach",
        "foreach": "@body('Executar_SQL')?['ResultSets']?['Table1']",
        "actions": {
            "Buscar_no_SharePoint": buscar_sharepoint,
            "Criar_ou_atualizar": upsert,
        },
        "runAfter": {"Executar_SQL": ["Succeeded"]},
    }

    condicao = {
        "type": "If",
        "expression": valid_expression,
        "actions": {
            "Executar_SQL": executar_sql,
            "Para_cada_resultado": resultados,
        },
        "else": {
            "actions": {
                "Rejeitar_identificador_invalido": {
                    "type": "Compose",
                    "inputs": {
                        "status": "rejected_before_sql",
                        "identifier": "@items('Para_cada_linha')?['Identificador']",
                        "correlation_id": "@parameters('CORRELATION_ID')",
                    },
                    "runAfter": {},
                }
            }
        },
        "runAfter": {},
    }

    return {
        "$schema": SCHEMA,
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$authentication": {"defaultValue": {}, "type": "SecureObject"},
            "$connections": {"defaultValue": {}, "type": "Object"},
            "CORRELATION_ID": {"defaultValue": correlation_id, "type": "String"},
        },
        "triggers": {
            "Recorrencia": {
                "type": "Recurrence",
                "recurrence": {"frequency": "Minute", "interval": 1},
            }
        },
        "actions": {
            "Listar_linhas": listar_linhas,
            "Para_cada_linha": {
                "type": "Foreach",
                "foreach": "@body('Listar_linhas')?['value']",
                "actions": {"Identificador_valido": condicao},
                "runAfter": {"Listar_linhas": ["Succeeded"]},
            },
        },
    }


def validar_definicao_real(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if definition.get("$schema") != SCHEMA:
        errors.append("schema_invalido")
    if not definition.get("triggers"):
        errors.append("gatilho_ausente")

    operations: set[tuple[str, str]] = set()
    raw_expressions: list[str] = []
    for name, action in _walk_actions(definition.get("actions", {})):
        if action.get("type") == "OpenApiConnection":
            host = action.get("inputs", {}).get("host", {})
            operations.add((str(host.get("apiId") or ""), str(host.get("operationId") or "")))
        expression = action.get("expression")
        if isinstance(expression, str):
            raw_expressions.append(expression)
        if name == "Rejeitar_identificador_invalido" and action.get("type") != "Compose":
            errors.append("rejeicao_invalida")

    required_operations = {
        (EXCEL_API, "GetItems"),
        (SQL_API, "ExecuteProcedure_V2"),
        (SHAREPOINT_API, "GetItems"),
        (SHAREPOINT_API, "PostItem"),
        (SHAREPOINT_API, "PatchItem"),
    }
    for api_id, operation_id in sorted(required_operations - operations):
        errors.append(f"operacao_ausente:{api_id}:{operation_id}")

    if not any("isInt(" in expression for expression in raw_expressions):
        errors.append("validacao_numerica_ausente")

    raw = repr(definition)
    for marker in ("CORRELATION_ID", "ChaveIntegracao", "ResultSets", "Table1"):
        if marker not in raw:
            errors.append(f"marcador_ausente:{marker}")

    return errors
