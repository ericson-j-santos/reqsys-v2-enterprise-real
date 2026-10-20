#!/usr/bin/env python3
"""Canário DEV mínimo para provar SemanticModel -> ExecuteQueries sem promover paridade.

Cria no máximo um SemanticModel fixo no workspace DEV já existente. Se o item
já existir, apenas lê e valida a definição; definição divergente bloqueia o
fluxo. Não atualiza, não exclui, não cria workspace/capacity/licença e não
toca HML/STG/PROD.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"
ENVIRONMENT = "development"
EXPECTED_REF = "refs/heads/main"
EXPECTED_EVENT = "workflow_dispatch"
AUTHORIZATION = "PUBLISH-DRE-SENTINEL-DEV"
WORKSPACE_NAME = "ReqSys - Observabilidade"
CANARY_NAME = "ReqSys DRE Sentinel DEV"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
POWERBI_BASE = "https://api.powerbi.com/v1.0/myorg"
_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MAX_BYTES = 2 * 1024 * 1024
LRO_TIMEOUT_SECONDS = 120.0
_FABRIC_WS = r"[0-9a-fA-F-]{36}"
_FABRIC_ITEM = r"[0-9a-fA-F-]{36}"
_ALLOWED_FABRIC_GET = re.compile(
    rf"^/v1/(?:workspaces|workspaces/{_FABRIC_WS}/semanticModels|operations/{_FABRIC_ITEM}(?:/result)?)$"
)
_ALLOWED_FABRIC_POST = re.compile(
    rf"^/v1/workspaces/{_FABRIC_WS}/semanticModels(?:/{_FABRIC_ITEM}/getDefinition)?$"
)
_ALLOWED_PBI_GET = re.compile(
    rf"^/v1\.0/myorg/(?:groups|groups/{_FABRIC_WS}/datasets)$"
)
_ALLOWED_PBI_POST = re.compile(
    rf"^/v1\.0/myorg/groups/{_FABRIC_WS}/datasets/{_FABRIC_ITEM}/executeQueries$"
)
LRO_TIMEOUT_SECONDS = 120.0
PBI_DISCOVERY_TIMEOUT_SECONDS = 90.0

Requester = Callable[
    [str, str, str, dict[str, Any] | None],
    tuple[int, dict[str, str], dict[str, Any]],
]


class CanaryError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _az(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["az", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _az_tsv(args: list[str]) -> str:
    result = _az(args)
    if result.returncode != 0:
        raise CanaryError("azure_cli_failed")
    value = (result.stdout or "").strip()
    if not value:
        raise CanaryError("azure_cli_empty")
    return value


def _token(resource: str) -> str:
    return _az_tsv([
        "account", "get-access-token",
        "--resource", resource,
        "--query", "accessToken",
        "--output", "tsv",
        "--only-show-errors",
    ])


def _safe_error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("errorCode") or error.get("code")
    else:
        code = payload.get("errorCode") or payload.get("code")
    value = str(code or "unknown")
    return value[:96] if re.fullmatch(r"[A-Za-z0-9_.:-]+", value) else "unknown"


def _validate_endpoint(method: str, url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        raise CanaryError("endpoint_not_allowed")
    if parsed.netloc == "api.fabric.microsoft.com":
        if method == "GET" and _ALLOWED_FABRIC_GET.fullmatch(parsed.path):
            if parsed.path == "/v1/workspaces":
                pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
                if len(pairs) != 1 or pairs[0][0] != "roles" or pairs[0][1] not in {
                    "Admin", "Member", "Contributor"
                }:
                    raise CanaryError("query_not_allowed")
            elif parsed.query:
                raise CanaryError("query_not_allowed")
            return
        if method == "POST" and _ALLOWED_FABRIC_POST.fullmatch(parsed.path):
            if parsed.path.endswith("/getDefinition"):
                if urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) != [("format", "TMSL")]:
                    raise CanaryError("query_not_allowed")
            elif parsed.query:
                raise CanaryError("query_not_allowed")
            return
        raise CanaryError("endpoint_not_allowed")
    if parsed.netloc == "api.powerbi.com":
        if method == "GET" and _ALLOWED_PBI_GET.fullmatch(parsed.path):
            if parsed.path == "/v1.0/myorg/groups":
                pairs = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
                if set(pairs) != {"$top", "$skip"} or not all(v.isdigit() for v in pairs.values()):
                    raise CanaryError("query_not_allowed")
            elif parsed.query:
                raise CanaryError("query_not_allowed")
            return
        if method == "POST" and _ALLOWED_PBI_POST.fullmatch(parsed.path) and not parsed.query:
            return
        raise CanaryError("endpoint_not_allowed")
    raise CanaryError("endpoint_not_allowed")


def _request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    _validate_endpoint(method, url)
    parsed = urllib.parse.urlsplit(url)
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise CanaryError("response_too_large")
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise CanaryError("invalid_json") from exc
            response_headers = {str(k).casefold(): str(v) for k, v in response.headers.items()}
            return response.status, response_headers, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(MAX_BYTES + 1)
            data = json.loads(raw.decode("utf-8")) if raw and len(raw) <= MAX_BYTES else {}
        except (UnicodeError, json.JSONDecodeError, OSError):
            data = {}
        finally:
            exc.close()
        return exc.code, {}, data if isinstance(data, dict) else {}
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, {}, {}


def _guid(value: object) -> str | None:
    return value.casefold() if isinstance(value, str) and _GUID.fullmatch(value) else None


def _parts() -> list[dict[str, str]]:
    pbism = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "5.0",
        "settings": {"qnaEnabled": False},
    }
    model = {
        "compatibilityLevel": 1702,
        "model": {
            "culture": "pt-BR",
            "sourceQueryCulture": "pt-BR",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "discourageImplicitMeasures": True,
            "annotations": [],
            "expressions": [],
            "functions": [],
            "perspectives": [],
            "relationships": [],
            "roles": [],
            "tables": [{
                "name": "_Medidas",
                "columns": [{
                    "name": "Chave",
                    "dataType": "int64",
                    "sourceColumn": "Chave",
                    "summarizeBy": "none",
                }],
                "measures": [{
                    "name": "Meta",
                    "expression": "0",
                    "formatString": "0",
                }],
                "partitions": [{
                    "name": "_Medidas",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": [
                            "let",
                            "    Fonte = #table(type table [Chave = Int64.Type], {{1}})",
                            "in",
                            "    Fonte",
                        ],
                    },
                }],
            }],
        },
    }
    result = []
    for path, value in (("definition.pbism", pbism), ("model.bim", model)):
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        result.append({
            "path": path,
            "payload": base64.b64encode(raw).decode("ascii"),
            "payloadType": "InlineBase64",
        })
    return result


def _definition_hash(parts: list[dict[str, str]]) -> str:
    normalized = sorted(
        (str(p.get("path")), str(p.get("payloadType")), str(p.get("payload")))
        for p in parts
    )
    return hashlib.sha256(
        json.dumps(normalized, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _decode_parts(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definition = data.get("definition")
    parts = definition.get("parts") if isinstance(definition, dict) else None
    if not isinstance(parts, list):
        raise CanaryError("definition_parts_missing")
    decoded: dict[str, dict[str, Any]] = {}
    for part in parts:
        if not isinstance(part, dict):
            continue
        path = part.get("path")
        if path not in {"definition.pbism", "model.bim"}:
            continue
        if part.get("payloadType") != "InlineBase64" or not isinstance(part.get("payload"), str):
            raise CanaryError("definition_part_invalid")
        try:
            raw = base64.b64decode(part["payload"], validate=True)
            value = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise CanaryError("definition_part_invalid") from exc
        if not isinstance(value, dict):
            raise CanaryError("definition_part_invalid")
        decoded[path] = value
    if set(decoded) != {"definition.pbism", "model.bim"}:
        raise CanaryError("definition_required_parts_missing")
    return decoded


def _verify_definition(data: dict[str, Any]) -> bool:
    decoded = _decode_parts(data)
    pbism = decoded["definition.pbism"]
    model = decoded["model.bim"]
    if (pbism.get("settings") or {}).get("qnaEnabled") is not False:
        return False
    root = model.get("model")
    tables = root.get("tables") if isinstance(root, dict) else None
    if not isinstance(tables, list):
        return False
    target = [t for t in tables if isinstance(t, dict) and t.get("name") == "_Medidas"]
    if len(target) != 1:
        return False
    table = target[0]
    measures = table.get("measures")
    columns = table.get("columns")
    partitions = table.get("partitions")
    if not isinstance(measures, list) or not isinstance(columns, list) or not isinstance(partitions, list):
        return False
    meta = [m for m in measures if isinstance(m, dict) and m.get("name") == "Meta"]
    chave = [c for c in columns if isinstance(c, dict) and c.get("name") == "Chave"]
    partition = [p for p in partitions if isinstance(p, dict) and p.get("name") == "_Medidas"]
    if len(meta) != 1 or len(chave) != 1 or len(partition) != 1:
        return False
    expression = meta[0].get("expression")
    if isinstance(expression, list):
        expression = "\n".join(str(x) for x in expression)
    if str(expression or "").strip() != "0":
        return False
    source = partition[0].get("source")
    source_expression = source.get("expression") if isinstance(source, dict) else None
    if isinstance(source_expression, list):
        source_expression = "\n".join(str(x) for x in source_expression)
    return (
        isinstance(source, dict)
        and source.get("type") == "m"
        and "#table(type table [Chave = Int64.Type], {{1}})" in str(source_expression or "")
    )


def _wait_lro(
    initial_status: int,
    initial_headers: dict[str, str],
    token: str,
    requester: Requester,
    *,
    timeout: float = LRO_TIMEOUT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if initial_status != 202:
        raise CanaryError("lro_not_expected")
    operation_id = _guid(initial_headers.get("x-ms-operation-id"))
    if operation_id is None:
        raise CanaryError("lro_operation_id_missing")
    state_url = f"{FABRIC_BASE}/operations/{operation_id}"
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        status, headers, body = requester("GET", state_url, token, None)
        if status != 200:
            raise CanaryError(f"lro_state_http_{status}")
        state = body.get("status")
        if state == "Succeeded":
            result_url = f"{FABRIC_BASE}/operations/{operation_id}/result"
            result_status, _, result = requester("GET", result_url, token, None)
            if result_status != 200:
                raise CanaryError(f"lro_result_http_{result_status}")
            return result
        if state == "Failed":
            raise CanaryError("lro_failed")
        retry = headers.get("retry-after", "1")
        try:
            seconds = max(0.0, min(10.0, float(retry)))
        except ValueError:
            seconds = 1.0
        sleep(seconds)
    raise CanaryError("lro_timeout")


def _list_semantic_models(
    workspace_id: str,
    fabric_token: str,
    requester: Requester,
) -> list[dict[str, Any]]:
    status, _, data = requester(
        "GET",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/semanticModels",
        fabric_token,
        None,
    )
    if status != 200 or not isinstance(data.get("value"), list):
        raise CanaryError(f"semantic_model_list_http_{status}")
    return [item for item in data["value"] if isinstance(item, dict)]


def _exact_named(items: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [item for item in items if item.get("displayName") == name]


def _get_definition(
    workspace_id: str,
    model_id: str,
    fabric_token: str,
    requester: Requester,
) -> dict[str, Any]:
    status, headers, data = requester(
        "POST",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/semanticModels/{model_id}/getDefinition?format=TMSL",
        fabric_token,
        {},
    )
    if status == 200:
        return data
    if status == 202:
        return _wait_lro(status, headers, fabric_token, requester)
    raise CanaryError(f"get_definition_http_{status}:{_safe_error_code(data)}")


def _find_workspace(
    fabric_token: str,
    requester: Requester,
) -> tuple[str, str]:
    matched: dict[str, str] = {}
    for role in ("Admin", "Member", "Contributor"):
        status, _, data = requester(
            "GET",
            f"{FABRIC_BASE}/workspaces?roles={role}",
            fabric_token,
            None,
        )
        if status != 200 or not isinstance(data.get("value"), list):
            raise CanaryError(f"workspace_role_http_{status}")
        for item in data["value"]:
            if not isinstance(item, dict) or item.get("displayName") != WORKSPACE_NAME:
                continue
            workspace_id = _guid(item.get("id"))
            if workspace_id:
                matched[workspace_id] = role
    if len(matched) != 1:
        raise CanaryError(f"workspace_exact_count_{len(matched)}")
    workspace_id, role = next(iter(matched.items()))
    return workspace_id, role


def _powerbi_workspace_shared(
    workspace_id: str,
    powerbi_token: str,
    requester: Requester,
) -> bool:
    status, _, data = requester(
        "GET",
        f"{POWERBI_BASE}/groups?$top=100&$skip=0",
        powerbi_token,
        None,
    )
    if status != 200 or not isinstance(data.get("value"), list):
        raise CanaryError(f"powerbi_groups_http_{status}")
    matches = [
        item for item in data["value"]
        if isinstance(item, dict) and _guid(item.get("id")) == workspace_id
    ]
    if len(matches) != 1:
        raise CanaryError(f"powerbi_workspace_exact_count_{len(matches)}")
    dedicated = matches[0].get("isOnDedicatedCapacity")
    read_only = matches[0].get("isReadOnly")
    if type(dedicated) is not bool or type(read_only) is not bool:
        raise CanaryError("powerbi_workspace_flags_missing")
    if read_only:
        raise CanaryError("powerbi_workspace_read_only")
    return dedicated is False


def _ensure_canary(
    workspace_id: str,
    fabric_token: str,
    requester: Requester,
) -> tuple[str, bool, bool]:
    existing = _exact_named(_list_semantic_models(workspace_id, fabric_token, requester), CANARY_NAME)
    if len(existing) > 1:
        raise CanaryError(f"canary_ambiguous_{len(existing)}")
    if len(existing) == 1:
        model_id = _guid(existing[0].get("id"))
        if model_id is None:
            raise CanaryError("canary_id_invalid")
        if not _verify_definition(
            _get_definition(workspace_id, model_id, fabric_token, requester)
        ):
            raise CanaryError("existing_canary_definition_mismatch")
        return model_id, False, True

    payload = {
        "displayName": CANARY_NAME,
        "description": "Canário DEV fixo para validar SemanticModel e ExecuteQueries; não é relatório de negócio.",
        "definition": {"format": "TMSL", "parts": _parts()},
    }
    status, headers, data = requester(
        "POST",
        f"{FABRIC_BASE}/workspaces/{workspace_id}/semanticModels",
        fabric_token,
        payload,
    )
    if status == 201:
        created = data
    elif status == 202:
        created = _wait_lro(status, headers, fabric_token, requester)
    else:
        raise CanaryError(f"create_semantic_model_http_{status}:{_safe_error_code(data)}")

    created_id = _guid(created.get("id"))
    if created_id is None:
        # Alguns LROs podem retornar uma forma reduzida; a listagem pós-condição é a fonte.
        created_id = ""
    after = _exact_named(_list_semantic_models(workspace_id, fabric_token, requester), CANARY_NAME)
    if len(after) != 1:
        raise CanaryError(f"canary_post_create_count_{len(after)}")
    model_id = _guid(after[0].get("id"))
    if model_id is None:
        raise CanaryError("canary_id_invalid")
    if created_id and created_id != model_id:
        raise CanaryError("canary_created_id_mismatch")
    verified = _verify_definition(
        _get_definition(workspace_id, model_id, fabric_token, requester)
    )
    if not verified:
        raise CanaryError("canary_definition_not_verified")
    return model_id, True, True


def _discover_powerbi_dataset(
    workspace_id: str,
    powerbi_token: str,
    requester: Requester,
    *,
    timeout: float = PBI_DISCOVERY_TIMEOUT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> str:
    deadline = monotonic() + timeout
    while True:
        status, _, data = requester(
            "GET",
            f"{POWERBI_BASE}/groups/{workspace_id}/datasets",
            powerbi_token,
            None,
        )
        if status == 200 and isinstance(data.get("value"), list):
            matches = [
                item for item in data["value"]
                if isinstance(item, dict) and item.get("name") == CANARY_NAME
            ]
            if len(matches) > 1:
                raise CanaryError(f"powerbi_canary_ambiguous_{len(matches)}")
            if len(matches) == 1:
                dataset_id = _guid(matches[0].get("id"))
                if dataset_id is None:
                    raise CanaryError("powerbi_canary_id_invalid")
                return dataset_id
        elif status not in {200, 404}:
            raise CanaryError(f"powerbi_dataset_list_http_{status}")
        if monotonic() >= deadline:
            raise CanaryError("powerbi_dataset_visibility_timeout")
        sleep(3.0)


def _execute_query(
    workspace_id: str,
    dataset_id: str,
    dax: str,
    powerbi_token: str,
    requester: Requester,
) -> tuple[int, dict[str, Any]]:
    status, _, data = requester(
        "POST",
        f"{POWERBI_BASE}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        powerbi_token,
        {
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    return status, data


def _single_value(data: dict[str, Any]) -> Any:
    try:
        rows = data["results"][0]["tables"][0]["rows"]
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise KeyError
        row = rows[0]
        if "[value]" in row:
            return row["[value]"]
        if len(row) == 1:
            return next(iter(row.values()))
    except (KeyError, IndexError, TypeError):
        pass
    raise CanaryError("execute_queries_response_invalid")


def execute(
    *,
    tenant_id: str,
    authorization: str,
    requester: Requester = _request,
) -> dict[str, Any]:
    if os.getenv("GITHUB_REF") != EXPECTED_REF:
        raise CanaryError("main_required")
    if os.getenv("GITHUB_EVENT_NAME") != EXPECTED_EVENT:
        raise CanaryError("workflow_dispatch_required")
    if authorization != AUTHORIZATION:
        raise CanaryError("authorization_invalid")
    active_tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    if active_tenant.casefold() != tenant_id.casefold() or tenant_id.casefold() != EXPECTED_TENANT.casefold():
        raise CanaryError("tenant_mismatch")

    fabric_token = _token(FABRIC_RESOURCE)
    powerbi_token = _token(POWERBI_RESOURCE)
    workspace_id, role = _find_workspace(fabric_token, requester)
    if role not in {"Admin", "Member", "Contributor"}:
        raise CanaryError("workspace_write_role_missing")
    shared = _powerbi_workspace_shared(workspace_id, powerbi_token, requester)

    model_id, created, definition_verified = _ensure_canary(
        workspace_id, fabric_token, requester
    )
    # Replay real da decisão: deve reutilizar o mesmo item e nunca criar/update.
    replay_id, replay_created, replay_verified = _ensure_canary(
        workspace_id, fabric_token, requester
    )
    if replay_id != model_id or replay_created or not replay_verified:
        raise CanaryError("canary_idempotency_failed")

    dataset_id = _discover_powerbi_dataset(
        workspace_id, powerbi_token, requester
    )
    status, data = _execute_query(
        workspace_id,
        dataset_id,
        'EVALUATE ROW("value", \'_Medidas\'[Meta])',
        powerbi_token,
        requester,
    )
    if status != 200:
        raise CanaryError(f"execute_queries_http_{status}:{_safe_error_code(data)}")
    value = _single_value(data)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) != 0.0:
        raise CanaryError("sentinel_value_mismatch")

    negative_status, _ = _execute_query(
        workspace_id,
        dataset_id,
        'EVALUATE ROW("value", [Medida Inexistente Controle DRE])',
        powerbi_token,
        requester,
    )
    if negative_status == 200:
        raise CanaryError("negative_control_failed")

    return {
        "schema": "reqsys/powerbi-dre-sentinel-dev/v1",
        "status": "passed",
        "environment": ENVIRONMENT,
        "source_sha": os.getenv("GITHUB_SHA", ""),
        "workspace_ref": _ref(workspace_id),
        "semantic_model_ref": _ref(model_id),
        "dataset_ref": _ref(dataset_id),
        "canary_ref": _ref(CANARY_NAME),
        "workspace_role": role,
        "workspace_existing": True,
        "workspace_shared_capacity": shared,
        "new_workspace_created": False,
        "new_capacity_or_license_requested": False,
        "billing_mutation_performed": False,
        "incremental_cost_verified_zero": False,
        "cost_policy": "no_purchase_or_capacity_creation; reject_on_license_or_capacity_error",
        "semantic_model_created": created,
        "semantic_model_definition_verified": definition_verified,
        "semantic_model_definition_hash": _definition_hash(_parts()),
        "idempotency_verified": True,
        "execute_queries_status": status,
        "sentinel_measure": "_Medidas[Meta]",
        "sentinel_value": value,
        "web_reference_value": 0,
        "sentinel_parity_passed": True,
        "negative_control_detected": True,
        "negative_control_http_status": negative_status,
        "metric_parity_promoted": False,
        "representative_business_metric": False,
        "production_touched": False,
        "stg_hml_touched": False,
        "secret_value_exposed": False,
        "raw_remote_ids_logged": False,
        "delete_performed": False,
        "update_definition_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = execute(
            tenant_id=args.tenant_id.strip(),
            authorization=args.authorization,
        )
        code = 0
    except (CanaryError, OSError, subprocess.SubprocessError) as exc:
        evidence = {
            "schema": "reqsys/powerbi-dre-sentinel-dev/v1",
            "status": "blocked",
            "blocker": str(exc).split(":", 1)[0],
            "environment": ENVIRONMENT,
            "source_sha": os.getenv("GITHUB_SHA", ""),
            "new_workspace_created": False,
            "new_capacity_or_license_requested": False,
            "billing_mutation_performed": False,
            "incremental_cost_verified_zero": False,
            "metric_parity_promoted": False,
            "production_touched": False,
            "stg_hml_touched": False,
            "secret_value_exposed": False,
            "raw_remote_ids_logged": False,
            "delete_performed": False,
            "update_definition_performed": False,
        }
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": evidence["status"],
        "blocker": evidence.get("blocker"),
        "semantic_model_created": evidence.get("semantic_model_created"),
        "definition_verified": evidence.get("semantic_model_definition_verified"),
        "sentinel_parity_passed": evidence.get("sentinel_parity_passed"),
        "metric_parity_promoted": False,
        "billing_mutation_performed": False,
        "raw_remote_ids_logged": False,
    }, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
