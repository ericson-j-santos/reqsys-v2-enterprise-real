#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Iterator

FLOW_NAMES = (
    "ReqSys - Notificar Teams (Tarefa criada no Planner)",
    "ReqSys - Notificar Teams (Tarefa concluída no Planner)",
)
FLOW_CARD_TITLES = {
    "ReqSys - Notificar Teams (Tarefa criada no Planner)": "Nova tarefa no Planner",
    "ReqSys - Notificar Teams (Tarefa concluída no Planner)": "Tarefa concluída no Planner",
}
REQUIRED_CONNECTIONS = {"shared_planner", "shared_teams"}
PLANNER_TASK_URL = (
    "https://planner.cloud.microsoft/webui/plan/"
    "@{parameters('PLANNER_PLAN_ID')}/view/board/task/@{triggerBody()?['id']}"
)
TEAMS_API = "/providers/Microsoft.PowerApps/apis/shared_teams"
TEAMS_POST_CARD_OPERATION = "PostCardToConversation"
NOTIFY_ACTION_NAME = "Notificar_Teams"
FILTER_ACTION_NAME = "Ignorar_tarefas_de_teste_automatizado"
EXPECTED_FILTER_ELSE = {"actions": {}}
WORKFLOW_SELECT = (
    "workflowid,workflowidunique,name,statecode,statuscode,componentstate,"
    "category,type,clientdata"
)


class FlowStateError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}


def required(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise FlowStateError(f"variavel_obrigatoria_ausente:{name}")
    return value


def request_json(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
    *,
    if_match: str | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        if method.upper() == "PATCH":
            headers["If-Match"] = if_match or "*"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def error_detail(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    code = str(error.get("code") or "")[:120]
    message = " ".join(str(error.get("message") or "").split())[:200]
    return f"{code}:{message}" if message else code


def select_flow(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if str(row.get("name") or "") == name
        and int(row.get("category", -1)) == 5
        and int(row.get("type", -1)) == 1
    ]
    if len(matches) != 1:
        raise FlowStateError(f"flow_ambiguo:{name}:{len(matches)}")
    return matches[0]


def parse_clientdata(row: dict[str, Any]) -> dict[str, Any]:
    raw = str(row.get("clientdata") or "")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FlowStateError("flow_clientdata_invalido") from exc
    if not isinstance(payload, dict):
        raise FlowStateError("flow_clientdata_invalido")
    return payload


def connection_keys(row: dict[str, Any]) -> list[str]:
    clientdata = parse_clientdata(row)
    props = clientdata.get("properties") if isinstance(clientdata, dict) else {}
    refs = props.get("connectionReferences") if isinstance(props, dict) else {}
    if not isinstance(refs, dict):
        raise FlowStateError("flow_connection_references_ausentes")
    keys = sorted(str(key) for key in refs)
    missing = sorted(REQUIRED_CONNECTIONS - set(keys))
    if missing:
        raise FlowStateError("flow_connection_references_incompletas:" + ",".join(missing))
    return keys


def desired_card(flow_name: str) -> dict[str, Any]:
    if flow_name not in FLOW_CARD_TITLES:
        raise FlowStateError(f"flow_card_titulo_desconhecido:{flow_name}")
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": FLOW_CARD_TITLES[flow_name],
            },
            {
                "type": "TextBlock",
                "wrap": True,
                "weight": "Bolder",
                "text": "@{triggerBody()?['title']}",
            },
            {
                "type": "FactSet",
                "facts": [
                    {
                        "title": "Progresso",
                        "value": "@{string(triggerBody()?['percentComplete'])}%",
                    },
                    {
                        "title": "Vencimento",
                        "value": "@{coalesce(triggerBody()?['dueDateTime'], 'Sem prazo')}",
                    },
                ],
            },
            {
                "type": "TextBlock",
                "wrap": True,
                "isSubtle": True,
                "spacing": "Small",
                "size": "Small",
                "text": "ID da tarefa: @{triggerBody()?['id']}",
            },
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "Abrir no Planner",
                "url": PLANNER_TASK_URL,
            }
        ],
    }


def _walk_actions(actions: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for name, action in actions.items():
        if not isinstance(action, dict):
            continue
        yield name, action
        nested = action.get("actions")
        if isinstance(nested, dict):
            yield from _walk_actions(nested)
        else_actions = action.get("else", {}).get("actions")
        if isinstance(else_actions, dict):
            yield from _walk_actions(else_actions)


def _notify_action(clientdata: dict[str, Any]) -> dict[str, Any]:
    properties = clientdata.get("properties")
    definition = properties.get("definition") if isinstance(properties, dict) else None
    actions = definition.get("actions") if isinstance(definition, dict) else None
    if not isinstance(actions, dict):
        raise FlowStateError("flow_definition_actions_ausentes")

    matches = [action for name, action in _walk_actions(actions) if name == NOTIFY_ACTION_NAME]
    if len(matches) != 1:
        raise FlowStateError(f"flow_notificar_teams_ambiguo:{len(matches)}")

    action = matches[0]
    host = action.get("inputs", {}).get("host", {})
    if (
        host.get("apiId") != TEAMS_API
        or host.get("operationId") != TEAMS_POST_CARD_OPERATION
    ):
        raise FlowStateError("flow_notificar_teams_operacao_invalida")

    parameters = action.get("inputs", {}).get("parameters", {})
    if "body/messageBody" not in parameters:
        raise FlowStateError("flow_card_message_body_ausente")
    return action


def ensure_filter_else_contract(clientdata: dict[str, Any]) -> bool:
    properties = clientdata.get("properties")
    definition = properties.get("definition") if isinstance(properties, dict) else None
    actions = definition.get("actions") if isinstance(definition, dict) else None
    if not isinstance(actions, dict):
        raise FlowStateError("flow_definition_actions_ausentes")

    filter_action = actions.get(FILTER_ACTION_NAME)
    if not isinstance(filter_action, dict) or filter_action.get("type") != "If":
        raise FlowStateError("flow_filtro_tarefa_teste_ausente")

    if "else" not in filter_action:
        filter_action["else"] = copy.deepcopy(EXPECTED_FILTER_ELSE)
        return True
    if filter_action.get("else") != EXPECTED_FILTER_ELSE:
        raise FlowStateError("flow_filtro_tarefa_teste_else_invalido")
    return False


def card_contract(clientdata: dict[str, Any]) -> dict[str, Any]:
    action = _notify_action(clientdata)
    raw = action["inputs"]["parameters"]["body/messageBody"]
    if not isinstance(raw, str):
        raise FlowStateError("flow_card_message_body_invalido")
    try:
        card = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FlowStateError("flow_card_message_body_invalido") from exc

    if not isinstance(card, dict) or card.get("type") != "AdaptiveCard":
        raise FlowStateError("flow_card_adaptive_card_ausente")

    facts: list[str] = []
    for block in card.get("body") or []:
        if not isinstance(block, dict) or block.get("type") != "FactSet":
            continue
        for fact in block.get("facts") or []:
            if isinstance(fact, dict):
                facts.append(str(fact.get("title") or ""))

    actions = [
        item
        for item in (card.get("actions") or [])
        if isinstance(item, dict)
        and item.get("type") == "Action.OpenUrl"
        and item.get("title") == "Abrir no Planner"
        and item.get("url") == PLANNER_TASK_URL
    ]
    body = card.get("body") or []
    title = ""
    if body and isinstance(body[0], dict):
        title = str(body[0].get("text") or "")

    return {
        "title": title,
        "facts": sorted(facts),
        "has_plan_fact": "Plano" in facts,
        "has_progress_fact": "Progresso" in facts,
        "has_open_planner": len(actions) == 1,
    }


def reconcile_card_clientdata(
    row: dict[str, Any],
    flow_name: str,
) -> tuple[str, bool, dict[str, Any], dict[str, Any]]:
    raw_before = str(row.get("clientdata") or "")
    before = parse_clientdata(row)
    before_contract = card_contract(before)

    after = copy.deepcopy(before)
    action = _notify_action(after)
    expected_body = json.dumps(desired_card(flow_name), ensure_ascii=False)
    current_body = action["inputs"]["parameters"]["body/messageBody"]
    card_changed = current_body != expected_body
    if card_changed:
        action["inputs"]["parameters"]["body/messageBody"] = expected_body

    filter_else_changed = ensure_filter_else_contract(after)
    changed = card_changed or filter_else_changed

    after_contract = card_contract(after)
    expected_contract = {
        "title": FLOW_CARD_TITLES[flow_name],
        "facts": ["Progresso", "Vencimento"],
        "has_plan_fact": False,
        "has_progress_fact": True,
        "has_open_planner": True,
    }
    if after_contract != expected_contract:
        raise FlowStateError(f"flow_card_contrato_invalido:{flow_name}")

    raw_after = raw_before if not changed else json.dumps(after, ensure_ascii=False)
    return raw_after, changed, before_contract, after_contract


def workflow_url(base: str, workflow_id: str) -> str:
    return f"{base.rstrip('/')}/api/data/v9.2/workflows({workflow_id})"


def discover(base: str, token: str, name: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "$select": WORKFLOW_SELECT,
            "$filter": f"category eq 5 and type eq 1 and name eq '{name.replace(chr(39), chr(39) * 2)}'",
            "$top": "2",
        }
    )
    status, payload = request_json(
        "GET",
        f"{base.rstrip('/')}/api/data/v9.2/workflows?{query}",
        token,
    )
    if status != 200:
        raise FlowStateError(f"dataverse_discovery_http_{status}")
    return select_flow(payload.get("value") or [], name)


def get_flow(base: str, token: str, workflow_id: str) -> dict[str, Any]:
    status, payload = request_json(
        "GET",
        workflow_url(base, workflow_id) + f"?$select={WORKFLOW_SELECT}",
        token,
    )
    if status != 200:
        raise FlowStateError(f"dataverse_get_http_{status}")
    return payload


def get_unpublished_flow(
    base: str,
    token: str,
    workflow_id: str,
) -> dict[str, Any]:
    status, payload = request_json(
        "GET",
        (
            workflow_url(base, workflow_id)
            + f"/Microsoft.Dynamics.CRM.RetrieveUnpublished()?$select={WORKFLOW_SELECT}"
        ),
        token,
    )
    if status != 200:
        raise FlowStateError(
            f"dataverse_retrieve_unpublished_http_{status}:{error_detail(payload)}"
        )
    return payload


def semantic_clientdata_fingerprint(raw: str) -> dict[str, Any]:
    raw_hash = hashlib.sha256(raw.encode()).hexdigest()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "invalid_json",
            "clientdata_sha256": raw_hash,
        }
    if not isinstance(payload, dict):
        return {
            "status": "invalid_payload",
            "clientdata_sha256": raw_hash,
        }

    normalized = copy.deepcopy(payload)
    try:
        action = _notify_action(normalized)
        parameters = action["inputs"]["parameters"]
        card_raw = parameters["body/messageBody"]
        if not isinstance(card_raw, str):
            raise FlowStateError("flow_card_message_body_invalido")
        card = json.loads(card_raw)
        if not isinstance(card, dict):
            raise FlowStateError("flow_card_message_body_invalido")
        contract = card_contract(normalized)
    except (FlowStateError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid_contract",
            "clientdata_sha256": raw_hash,
            "error": str(exc)[:160] or exc.__class__.__name__,
        }

    card_canonical = json.dumps(
        card,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    parameters["body/messageBody"] = "__REQSYS_CARD_BODY__"
    non_card_canonical = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "status": "ok",
        "clientdata_sha256": raw_hash,
        "non_card_sha256": hashlib.sha256(non_card_canonical.encode()).hexdigest(),
        "card_canonical_sha256": hashlib.sha256(card_canonical.encode()).hexdigest(),
        "card_contract": contract,
    }


def _non_card_payload(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise FlowStateError("flow_clientdata_invalido")
    normalized = copy.deepcopy(payload)
    action = _notify_action(normalized)
    parameters = action["inputs"]["parameters"]
    parameters["body/messageBody"] = "__REQSYS_CARD_BODY__"
    return normalized


def _json_pointer_segment(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _safe_value_hash(value: Any) -> str:
    if value is _MISSING:
        raw = "__REQSYS_MISSING__"
    else:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(raw.encode()).hexdigest()


def _safe_value_type(value: Any) -> str:
    if value is _MISSING:
        return "missing"
    if value is None:
        return "null"
    return type(value).__name__


_MISSING = object()


def non_card_structural_diff(
    published_raw: str,
    unpublished_raw: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    published = _non_card_payload(published_raw)
    unpublished = _non_card_payload(unpublished_raw)
    items: list[dict[str, Any]] = []
    total = 0

    def walk(before: Any, after: Any, path: str) -> None:
        nonlocal total
        if before is not _MISSING and after is not _MISSING and before == after:
            return

        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(set(before) | set(after)):
                segment = _json_pointer_segment(str(key))
                walk(
                    before.get(key, _MISSING),
                    after.get(key, _MISSING),
                    f"{path}/{segment}",
                )
            return

        if isinstance(before, list) and isinstance(after, list):
            for index in range(max(len(before), len(after))):
                walk(
                    before[index] if index < len(before) else _MISSING,
                    after[index] if index < len(after) else _MISSING,
                    f"{path}/{index}",
                )
            return

        total += 1
        if len(items) < limit:
            items.append(
                {
                    "path": path or "/",
                    "published_type": _safe_value_type(before),
                    "unpublished_type": _safe_value_type(after),
                    "published_value_sha256": _safe_value_hash(before),
                    "unpublished_value_sha256": _safe_value_hash(after),
                }
            )

    walk(published, unpublished, "")
    return {
        "count": total,
        "truncated": total > limit,
        "paths": items,
    }


def unpublished_diagnostic(
    published: dict[str, Any],
    desired_raw: str,
    unpublished: dict[str, Any],
) -> dict[str, Any]:
    published_raw = str(published.get("clientdata") or "")
    unpublished_raw = str(unpublished.get("clientdata") or "")

    published_fp = semantic_clientdata_fingerprint(published_raw)
    desired_fp = semantic_clientdata_fingerprint(desired_raw)
    unpublished_fp = semantic_clientdata_fingerprint(unpublished_raw)

    if unpublished_raw == published_raw:
        relation = "same_as_published"
    elif unpublished_raw == desired_raw:
        relation = "same_as_desired"
    elif unpublished_fp.get("status") != "ok":
        relation = "unpublished_invalid"
    elif published_fp.get("status") != "ok" or desired_fp.get("status") != "ok":
        relation = "reference_invalid"
    elif (
        unpublished_fp.get("non_card_sha256") == desired_fp.get("non_card_sha256")
        and unpublished_fp.get("card_canonical_sha256")
        == desired_fp.get("card_canonical_sha256")
    ):
        relation = "same_as_desired_semantic"
    elif unpublished_fp.get("non_card_sha256") != published_fp.get("non_card_sha256"):
        relation = "non_card_divergent"
    elif (
        unpublished_fp.get("card_canonical_sha256")
        == desired_fp.get("card_canonical_sha256")
    ):
        relation = "same_non_card_desired_card"
    elif (
        unpublished_fp.get("card_canonical_sha256")
        == published_fp.get("card_canonical_sha256")
    ):
        relation = "same_non_card_published_card"
    else:
        relation = "card_only_divergent"

    diagnostic = {
        "unpublished_detected": True,
        "unpublished_relation": relation,
        "published_fingerprint": published_fp,
        "desired_fingerprint": desired_fp,
        "unpublished_fingerprint": unpublished_fp,
        "unpublished_componentstate": unpublished.get("componentstate"),
    }
    if (
        published_fp.get("status") == "ok"
        and unpublished_fp.get("status") == "ok"
    ):
        diagnostic["non_card_diff"] = non_card_structural_diff(
            published_raw,
            unpublished_raw,
        )
    return diagnostic


def patch_clientdata(
    base: str,
    token: str,
    row: dict[str, Any],
    clientdata: str,
) -> None:
    workflow_id = str(row.get("workflowid") or "").strip()
    etag = str(row.get("@odata.etag") or "").strip()
    if not workflow_id:
        raise FlowStateError("workflowid_ausente")
    if not etag:
        raise FlowStateError("flow_etag_ausente")

    status, payload = request_json(
        "PATCH",
        workflow_url(base, workflow_id),
        token,
        {"clientdata": clientdata},
        if_match=etag,
    )
    if status != 204:
        raise FlowStateError(f"dataverse_card_patch_http_{status}:{error_detail(payload)}")


def publish_workflow(base: str, token: str, workflow_id: str) -> None:
    try:
        canonical_id = str(uuid.UUID(workflow_id))
    except ValueError as exc:
        raise FlowStateError("workflowid_invalido") from exc

    parameter_xml = (
        "<importexportxml><workflows><workflow>"
        + canonical_id
        + "</workflow></workflows></importexportxml>"
    )
    status, payload = request_json(
        "POST",
        f"{base.rstrip('/')}/api/data/v9.2/PublishXml",
        token,
        {"ParameterXml": parameter_xml},
    )
    if status not in {200, 204}:
        raise FlowStateError(
            f"dataverse_publish_workflow_http_{status}:{error_detail(payload)}"
        )


def reconcile_flow_card(
    base: str,
    token: str,
    row: dict[str, Any],
    flow_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_before = str(row.get("clientdata") or "")
    before_hash = hashlib.sha256(raw_before.encode()).hexdigest()
    desired_raw, changed, before_contract, desired_contract = reconcile_card_clientdata(
        row,
        flow_name,
    )
    if not changed:
        return row, {
            "card_reconciled": False,
            "flow_direct_patch_used": False,
            "flow_deactivated_for_patch": False,
            "flow_unpublished_revision_used": False,
            "flow_publish_xml_used": False,
            "clientdata_before_sha256": before_hash,
            "card_before": before_contract,
            "card_after": desired_contract,
        }

    workflow_id = str(row.get("workflowid") or "").strip()
    if not workflow_id:
        raise FlowStateError("workflowid_ausente")

    # Atualiza o registro corrente diretamente. Desativar o flow apenas para editar
    # cria uma camada unpublished e pode fazer o PATCH subsequente ser interpretado
    # como published update em conflito (Dataverse 0x80040203).
    # Se ja existir uma revisao unpublished concorrente, o PATCH falha fechado e
    # nenhuma mudanca de estado e tentada automaticamente.
    try:
        after, observed_contract = _patch_and_verify(
            base,
            token,
            row,
            workflow_id,
            desired_raw,
            desired_contract,
            raw_before,
            before_hash,
        )
    except FlowStateError as exc:
        message = str(exc)
        if (
            "dataverse_card_patch_http_400:0x80040203:" in message
            and "unpublished active row" in message.lower()
        ):
            unpublished = get_unpublished_flow(base, token, workflow_id)
            details = unpublished_diagnostic(row, desired_raw, unpublished)
            relation = details.get("unpublished_relation")
            unpublished_workflow_id = str(unpublished.get("workflowid") or "").strip()
            unpublished_componentstate = int(unpublished.get("componentstate", -1))

            if (
                relation not in {"same_as_desired", "same_as_desired_semantic"}
                or unpublished_workflow_id != workflow_id
                or unpublished_componentstate != 1
            ):
                raise FlowStateError(message, details=details) from exc

            # O draft só é publicado quando já corresponde semanticamente ao
            # estado desejado completo. Qualquer divergência adicional continua
            # falhando fechado para não promover mudança externa concorrente.
            publish_workflow(base, token, workflow_id)
            after = get_flow(base, token, workflow_id)
            if int(after.get("componentstate", -1)) != 0:
                raise FlowStateError(
                    "flow_unpublished_publish_componentstate_invalido",
                    details=details,
                )

            observed_contract = card_contract(parse_clientdata(after))
            if observed_contract != desired_contract:
                raise FlowStateError(
                    "flow_unpublished_publish_card_divergente",
                    details=details,
                )

            desired_fp = semantic_clientdata_fingerprint(desired_raw)
            observed_fp = semantic_clientdata_fingerprint(
                str(after.get("clientdata") or "")
            )
            if (
                desired_fp.get("status") != "ok"
                or observed_fp.get("status") != "ok"
                or observed_fp.get("non_card_sha256")
                != desired_fp.get("non_card_sha256")
                or observed_fp.get("card_canonical_sha256")
                != desired_fp.get("card_canonical_sha256")
            ):
                raise FlowStateError(
                    "flow_unpublished_publish_semantic_divergente",
                    details=details,
                )

            return after, {
                "card_reconciled": True,
                "flow_direct_patch_used": False,
                "flow_deactivated_for_patch": False,
                "flow_unpublished_revision_used": True,
                "flow_publish_xml_used": True,
                "clientdata_before_sha256": before_hash,
                "card_before": before_contract,
                "card_after": observed_contract,
            }
        raise

    return after, {
        "card_reconciled": True,
        "flow_direct_patch_used": True,
        "flow_deactivated_for_patch": False,
        "flow_unpublished_revision_used": False,
        "flow_publish_xml_used": False,
        "clientdata_before_sha256": before_hash,
        "card_before": before_contract,
        "card_after": observed_contract,
    }



def _patch_and_verify(
    base: str,
    token: str,
    row: dict[str, Any],
    workflow_id: str,
    desired_raw: str,
    desired_contract: dict[str, Any],
    raw_before: str,
    before_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    patch_clientdata(base, token, row, desired_raw)
    after = get_flow(base, token, workflow_id)

    try:
        observed_contract = card_contract(parse_clientdata(after))
        if observed_contract != desired_contract:
            raise FlowStateError("flow_card_verificacao_pos_patch_falhou")
    except Exception as verify_error:
        rollback_error: Exception | None = None
        try:
            patch_clientdata(base, token, after, raw_before)
            rolled_back = get_flow(base, token, workflow_id)
            if hashlib.sha256(str(rolled_back.get("clientdata") or "").encode()).hexdigest() != before_hash:
                raise FlowStateError("flow_card_rollback_hash_divergente")
        except Exception as exc:
            rollback_error = exc
        if rollback_error is not None:
            raise FlowStateError(
                f"flow_card_patch_invalido_rollback_falhou:{rollback_error}"
            ) from verify_error
        raise FlowStateError("flow_card_patch_invalido_rollback_aplicado") from verify_error

    return after, observed_contract



def activate(base: str, token: str, workflow_id: str) -> None:
    status, payload = request_json(
        "PATCH",
        workflow_url(base, workflow_id),
        token,
        {"statecode": 1, "statuscode": 2},
    )
    if status != 204:
        raise FlowStateError(f"dataverse_activate_http_{status}:{error_detail(payload)}")



def ensure_active(
    base: str,
    token: str,
    row: dict[str, Any],
    attempts: int = 18,
    delay_seconds: int = 5,
) -> dict[str, Any]:
    workflow_id = str(row.get("workflowid") or "").strip()
    if not workflow_id:
        raise FlowStateError("workflowid_ausente")
    if int(row.get("statecode", -1)) != 1:
        activate(base, token, workflow_id)
    last = row
    for _ in range(attempts):
        last = get_flow(base, token, workflow_id)
        if int(last.get("statecode", -1)) == 1 and int(last.get("statuscode", -1)) == 2:
            return last
        time.sleep(delay_seconds)
    raise FlowStateError(f"flow_activation_timeout:{workflow_id}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcilia o cartão e garante flows Planner→Teams DEV ativos via OIDC/Dataverse"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    base = required("PLANNER_TEAMS_DATAVERSE_URL")
    token = required("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN")
    evidence: dict[str, Any] = {
        "schema_version": "1.5.0",
        "environment": "dev",
        "auth_mode": "github_oidc_dataverse",
        "status": "running",
        "flows": [],
        "error": None,
    }

    try:
        for name in FLOW_NAMES:
            discovered = discover(base, token, name)
            state_before = discovered.get("statecode")
            status_before = discovered.get("statuscode")
            refs = connection_keys(discovered)

            reconciled, card_evidence = reconcile_flow_card(
                base,
                token,
                discovered,
                name,
            )
            raw_reconciled = str(reconciled.get("clientdata") or "")
            reconciled_hash = hashlib.sha256(raw_reconciled.encode()).hexdigest()

            after = ensure_active(base, token, reconciled)
            raw_after = str(after.get("clientdata") or "")
            after_hash = hashlib.sha256(raw_after.encode()).hexdigest()
            if reconciled_hash != after_hash:
                raise FlowStateError(f"flow_clientdata_mudou_ao_ativar:{name}")

            observed_contract = card_contract(parse_clientdata(after))
            if observed_contract != card_evidence["card_after"]:
                raise FlowStateError(f"flow_card_mudou_ao_ativar:{name}")

            evidence["flows"].append(
                {
                    "workflowid": after.get("workflowid"),
                    "name": after.get("name"),
                    "state_before": state_before,
                    "status_before": status_before,
                    "state_after": after.get("statecode"),
                    "status_after": after.get("statuscode"),
                    "connection_reference_keys": refs,
                    **card_evidence,
                    "clientdata_sha256": after_hash,
                    "clientdata_preserved": True,
                }
            )
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        error: dict[str, Any] = {
            "type": exc.__class__.__name__,
            "message": str(exc)[:500],
        }
        if isinstance(exc, FlowStateError) and exc.details:
            error["details"] = exc.details
        evidence["error"] = error

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "flows": [
                    {
                        "name": item.get("name"),
                        "state_before": item.get("state_before"),
                        "state_after": item.get("state_after"),
                        "card_reconciled": item.get("card_reconciled"),
                        "flow_direct_patch_used": item.get("flow_direct_patch_used"),
                        "card_after": item.get("card_after"),
                        "clientdata_preserved": item.get("clientdata_preserved"),
                    }
                    for item in evidence["flows"]
                ],
                "error": evidence["error"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
