#!/usr/bin/env python3
"""E2E governado Power Automate -> Outlook em DEV.

Executa dentro do container API do ReqSys para reutilizar apenas a identidade
já resolvida pelo secret store do runtime. Nunca imprime ou persiste segredos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.core.secrets import describe_secret_resolution

DATAVERSE_URL = "https://orga258f260.crm2.dynamics.com"
FLOW_API = "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple"
FLOW_API_VERSION = "2016-11-01"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

FLOW_NAME = "PA-E2E - Change 1842 Outlook Idempotency 20260928"
EVENT_SUBJECT = "[PA-E2E CHANGE 1842] Revisao pos-aprovacao 20260928"
IDEMPOTENCY_KEY = "CHANGE-1842-CALENDAR-REVIEW-PA-E2E-20260928-V1"
EVENT_START = "2026-09-30T14:00:00"
EVENT_END = "2026-09-30T14:30:00"
OUTLOOK_API_ID = "/providers/Microsoft.PowerApps/apis/shared_office365"
OUTLOOK_CONNECTION_KEY = "shared_office365"

TERMINAL_SUCCESS = {"succeeded"}
TERMINAL_FAILURE = {"failed", "cancelled", "canceled", "timedout", "timedout", "skipped"}


class E2EError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_error(exc: BaseException) -> str:
    value = f"{type(exc).__name__}:{exc}"
    value = value.replace(settings.azure_client_secret or "__never__", "***")
    return value[:1200]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def token(client: httpx.Client, scope: str) -> str:
    if not settings.azure_tenant_id or not settings.azure_client_id or not settings.azure_client_secret:
        raise E2EError("AZURE_IDENTITY_INCOMPLETE")
    response = client.post(
        TOKEN_URL.format(tenant=settings.azure_tenant_id),
        data={
            "grant_type": "client_credentials",
            "client_id": settings.azure_client_id,
            "client_secret": settings.azure_client_secret,
            "scope": scope,
        },
        timeout=30,
    )
    response.raise_for_status()
    access_token = str(response.json().get("access_token") or "")
    if not access_token:
        raise E2EError("ACCESS_TOKEN_MISSING")
    return access_token


def headers(bearer: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }


def text(value: Any) -> str:
    return str(value or "").strip()


def environment_id(item: dict[str, Any]) -> str:
    props = item.get("properties") or {}
    raw = text(props.get("environmentId")) or text(item.get("name")) or text(item.get("id"))
    return raw.rstrip("/").split("/")[-1]


def environment_name(item: dict[str, Any]) -> str:
    props = item.get("properties") or {}
    linked = props.get("linkedEnvironmentMetadata") or {}
    return (
        text(item.get("displayName"))
        or text(props.get("displayName"))
        or text(linked.get("instanceName"))
        or text(item.get("name"))
    )


def environment_url(item: dict[str, Any]) -> str:
    props = item.get("properties") or {}
    linked = props.get("linkedEnvironmentMetadata") or {}
    return (
        text(item.get("url"))
        or text(props.get("environmentUrl"))
        or text(linked.get("instanceUrl"))
        or text(linked.get("instanceApiUrl"))
    ).rstrip("/")


def environment_sku(item: dict[str, Any]) -> str:
    props = item.get("properties") or {}
    return text(props.get("environmentSku") or props.get("environmentType") or item.get("type"))


def validate_runtime_is_dev(evidence: dict[str, Any]) -> None:
    app_env = text(settings.app_environment).casefold()
    public_env = text(settings.public_environment).casefold()
    combined = f"{app_env} {public_env}"
    if settings.is_production or any(marker in combined for marker in ("prod", "prd", "production", "producao", "produção")):
        raise E2EError("RUNTIME_NOT_DEV")
    evidence["runtime_environment"] = {
        "app_environment": app_env,
        "public_environment": public_env,
        "production": False,
    }


def discover_dev_environment(client: httpx.Client, flow_token: str) -> dict[str, Any]:
    response = client.get(
        f"{FLOW_API}/environments?api-version={FLOW_API_VERSION}",
        headers={"Authorization": f"Bearer {flow_token}", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    items = [item for item in response.json().get("value", []) if isinstance(item, dict)]
    configured_id = text(settings.powerautomate_env_id).casefold()
    target_url = DATAVERSE_URL.casefold()

    matches: list[dict[str, Any]] = []
    for item in items:
        eid = environment_id(item).casefold()
        eurl = environment_url(item).casefold()
        linked_blob = json.dumps(item.get("properties") or {}, ensure_ascii=False, default=str).casefold()
        by_url = bool(eurl and eurl == target_url) or "orga258f260.crm2.dynamics.com" in linked_blob
        by_id = bool(configured_id and eid == configured_id)
        if by_url or by_id:
            matches.append(item)

    if len(matches) != 1:
        raise E2EError(f"POWER_PLATFORM_DEV_ENVIRONMENT_AMBIGUOUS:{len(matches)}")

    selected = matches[0]
    name = environment_name(selected)
    sku = environment_sku(selected)
    classifier = f"{name} {sku} {environment_url(selected)}".casefold()
    if any(marker in classifier for marker in ("prod", "production", "producao", "produção")):
        raise E2EError("POWER_PLATFORM_TARGET_LOOKS_PRODUCTION")
    if "dev" not in classifier and sku.casefold() not in {"sandbox", "developer", "trial"}:
        raise E2EError(f"POWER_PLATFORM_TARGET_NOT_PROVEN_DEV:name={name}:sku={sku}")

    return {
        "id": environment_id(selected),
        "name": name,
        "sku": sku,
        "url": environment_url(selected),
    }


def discover_outlook_reference(client: httpx.Client, dv_token: str) -> dict[str, str]:
    params = {
        "$select": "connectionreferenceid,connectionreferencelogicalname,connectionid,connectorid,displayname,statecode",
    }
    response = client.get(
        f"{DATAVERSE_URL}/api/data/v9.2/connectionreferences",
        params=params,
        headers=headers(dv_token),
        timeout=30,
    )
    response.raise_for_status()
    usable: list[dict[str, Any]] = []
    for item in response.json().get("value", []):
        connector = text(item.get("connectorid")).casefold()
        logical = text(item.get("connectionreferencelogicalname"))
        connection_id = text(item.get("connectionid"))
        if "/shared_office365" in connector and logical and connection_id:
            usable.append(item)

    if len(usable) != 1:
        raise E2EError(f"OUTLOOK_REFERENCE_AMBIGUOUS:{len(usable)}")

    item = usable[0]
    return {
        "id": text(item.get("connectionreferenceid")),
        "logical_name": text(item.get("connectionreferencelogicalname")),
        "connection_id": text(item.get("connectionid")),
        "display_name": text(item.get("displayname")),
        "connector_id": text(item.get("connectorid")),
        "statecode": text(item.get("statecode")),
    }


def outlook_inputs(operation_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": {
            "connectionName": OUTLOOK_CONNECTION_KEY,
            "operationId": operation_id,
            "apiId": OUTLOOK_API_ID,
        },
        "parameters": parameters,
        "authentication": "@parameters('$authentication')",
    }


def build_clientdata(connection_reference_logical_name: str) -> dict[str, Any]:
    calendar_expr = "@first(body('Get_calendars_V2')?['value'])?['id']"
    subject_filter = f"subject eq '{EVENT_SUBJECT.replace(chr(39), chr(39) * 2)}'"
    body_initial = (
        "Power Automate E2E idempotency practice.<br>"
        f"IdempotencyKey: {IDEMPOTENCY_KEY}<br>"
        "Pass1Created=true"
    )
    body_validated = (
        "Power Automate E2E idempotency practice.<br>"
        f"IdempotencyKey: {IDEMPOTENCY_KEY}<br>"
        "Pass1CreatedOrReused=true<br>"
        "SecondPassValidated=true"
    )

    create_parameters = {
        "table": calendar_expr,
        "subject": EVENT_SUBJECT,
        "start": EVENT_START,
        "end": EVENT_END,
        "timeZone": "UTC",
        "body": body_initial,
        "showAs": "free",
        "responseRequested": False,
        "isReminderOn": False,
    }
    update_parameters = {
        "table": calendar_expr,
        "id": "@variables('EventId')",
        "subject": EVENT_SUBJECT,
        "start": EVENT_START,
        "end": EVENT_END,
        "timeZone": "UTC",
        "body": body_validated,
        "showAs": "free",
        "responseRequested": False,
        "isReminderOn": False,
    }

    definition: dict[str, Any] = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$connections": {"defaultValue": {}, "type": "Object"},
            "$authentication": {"defaultValue": {}, "type": "SecureObject"},
        },
        "triggers": {
            "Recurrence": {
                "type": "Recurrence",
                "recurrence": {"frequency": "Minute", "interval": 1},
            }
        },
        "actions": {
            "Get_calendars_V2": {
                "type": "OpenApiConnection",
                "runAfter": {},
                "inputs": outlook_inputs("CalendarGetTables_V2", {}),
            },
            "Init_EventId": {
                "type": "InitializeVariable",
                "runAfter": {"Get_calendars_V2": ["Succeeded"]},
                "inputs": {"variables": [{"name": "EventId", "type": "string", "value": ""}]},
            },
            "Get_events_pass1": {
                "type": "OpenApiConnection",
                "runAfter": {"Init_EventId": ["Succeeded"]},
                "inputs": outlook_inputs(
                    "V4CalendarGetItems",
                    {"table": calendar_expr, "$filter": subject_filter, "$top": 10},
                ),
            },
            "Pass1_create_if_missing": {
                "type": "If",
                "runAfter": {"Get_events_pass1": ["Succeeded"]},
                "expression": {
                    "and": [
                        {"equals": ["@length(body('Get_events_pass1')?['value'])", 0]}
                    ]
                },
                "actions": {
                    "Create_event_V4": {
                        "type": "OpenApiConnection",
                        "runAfter": {},
                        "inputs": outlook_inputs("V4CalendarPostItem", create_parameters),
                    },
                    "Set_EventId_created": {
                        "type": "SetVariable",
                        "runAfter": {"Create_event_V4": ["Succeeded"]},
                        "inputs": {
                            "name": "EventId",
                            "value": "@body('Create_event_V4')?['id']",
                        },
                    },
                },
                "else": {
                    "actions": {
                        "Set_EventId_existing": {
                            "type": "SetVariable",
                            "runAfter": {},
                            "inputs": {
                                "name": "EventId",
                                "value": "@first(body('Get_events_pass1')?['value'])?['id']",
                            },
                        }
                    }
                },
            },
            "Delay_before_pass2": {
                "type": "Wait",
                "runAfter": {"Pass1_create_if_missing": ["Succeeded"]},
                "inputs": {"interval": {"count": 5, "unit": "Second"}},
            },
            "Get_events_pass2": {
                "type": "OpenApiConnection",
                "runAfter": {"Delay_before_pass2": ["Succeeded"]},
                "inputs": outlook_inputs(
                    "V4CalendarGetItems",
                    {"table": calendar_expr, "$filter": subject_filter, "$top": 10},
                ),
            },
            "Pass2_require_exactly_one": {
                "type": "If",
                "runAfter": {"Get_events_pass2": ["Succeeded"]},
                "expression": {
                    "and": [
                        {"equals": ["@length(body('Get_events_pass2')?['value'])", 1]}
                    ]
                },
                "actions": {
                    "Set_EventId_pass2": {
                        "type": "SetVariable",
                        "runAfter": {},
                        "inputs": {
                            "name": "EventId",
                            "value": "@first(body('Get_events_pass2')?['value'])?['id']",
                        },
                    },
                    "Update_event_pass2_evidence": {
                        "type": "OpenApiConnection",
                        "runAfter": {"Set_EventId_pass2": ["Succeeded"]},
                        "inputs": outlook_inputs("V4CalendarPatchItem", update_parameters),
                    },
                },
                "else": {
                    "actions": {
                        "Fail_duplicate_or_missing": {
                            "type": "Terminate",
                            "runAfter": {},
                            "inputs": {
                                "runStatus": "Failed",
                                "runError": {
                                    "code": "IDEMPOTENCY_COUNT_INVALID",
                                    "message": "Second pass did not find exactly one event.",
                                },
                            },
                        }
                    }
                },
            },
            "E2E_result": {
                "type": "Compose",
                "runAfter": {"Pass2_require_exactly_one": ["Succeeded"]},
                "inputs": {
                    "eventId": "@variables('EventId')",
                    "idempotencyKey": IDEMPOTENCY_KEY,
                    "secondPassValidated": True,
                },
            },
        },
        "outputs": {},
    }

    return {
        "properties": {
            "connectionReferences": {
                OUTLOOK_CONNECTION_KEY: {
                    "runtimeSource": "embedded",
                    "connection": {
                        "connectionReferenceLogicalName": connection_reference_logical_name,
                    },
                    "api": {"name": OUTLOOK_CONNECTION_KEY},
                }
            },
            "definition": definition,
            "templateName": None,
        },
        "schemaVersion": "1.0.0.0",
    }


def find_flow(client: httpx.Client, dv_token: str) -> dict[str, Any] | None:
    params = {
        "$filter": f"name eq '{FLOW_NAME.replace(chr(39), chr(39) * 2)}' and category eq 5",
        "$select": "workflowid,workflowidunique,name,statecode,statuscode,modifiedon,clientdata",
        "$top": "2",
    }
    response = client.get(
        f"{DATAVERSE_URL}/api/data/v9.2/workflows",
        params=params,
        headers=headers(dv_token),
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json().get("value", [])
    if len(rows) > 1:
        raise E2EError(f"FLOW_NAME_AMBIGUOUS:{len(rows)}")
    return rows[0] if rows else None


def read_flow(client: httpx.Client, dv_token: str, workflow_id: str) -> dict[str, Any]:
    response = client.get(
        f"{DATAVERSE_URL}/api/data/v9.2/workflows({workflow_id})",
        params={"$select": "workflowid,workflowidunique,name,statecode,statuscode,modifiedon"},
        headers=headers(dv_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def set_flow_state(
    client: httpx.Client,
    dv_token: str,
    workflow_id: str,
    statecode: int,
) -> dict[str, Any]:
    response = client.patch(
        f"{DATAVERSE_URL}/api/data/v9.2/workflows({workflow_id})",
        json={"statecode": statecode},
        headers={**headers(dv_token), "If-Match": "*"},
        timeout=30,
    )
    response.raise_for_status()
    current = read_flow(client, dv_token, workflow_id)
    if int(current.get("statecode", -1)) != statecode:
        raise E2EError(
            f"FLOW_STATE_READBACK_MISMATCH:expected={statecode}:observed={current.get('statecode')}"
        )
    return current


def upsert_flow(
    client: httpx.Client,
    dv_token: str,
    connection_reference_logical_name: str,
    correlation_id: str,
) -> tuple[dict[str, Any], bool]:
    existing = find_flow(client, dv_token)
    clientdata = json.dumps(
        build_clientdata(connection_reference_logical_name),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    created = existing is None

    if existing is None:
        payload = {
            "category": 5,
            "name": FLOW_NAME,
            "type": 1,
            "description": f"Governed DEV E2E practice. correlation_id={correlation_id}",
            "primaryentity": "none",
            "clientdata": clientdata,
        }
        response = client.post(
            f"{DATAVERSE_URL}/api/data/v9.2/workflows",
            json=payload,
            headers=headers(dv_token),
            timeout=45,
        )
        response.raise_for_status()
        entity_id = text(response.headers.get("OData-EntityId") or response.headers.get("odata-entityid"))
        marker = "workflows("
        if marker not in entity_id:
            raise E2EError("CREATE_FLOW_ENTITY_ID_MISSING")
        workflow_id = entity_id.split(marker, 1)[1].split(")", 1)[0]
        existing = read_flow(client, dv_token, workflow_id)
    else:
        workflow_id = text(existing.get("workflowid"))
        if int(existing.get("statecode", 0)) == 1:
            set_flow_state(client, dv_token, workflow_id, 0)
        response = client.patch(
            f"{DATAVERSE_URL}/api/data/v9.2/workflows({workflow_id})",
            json={
                "clientdata": clientdata,
                "description": f"Governed DEV E2E practice. correlation_id={correlation_id}",
            },
            headers={**headers(dv_token), "If-Match": "*"},
            timeout=45,
        )
        response.raise_for_status()
        existing = read_flow(client, dv_token, workflow_id)

    return existing, created


def run_status(run: dict[str, Any]) -> str:
    props = run.get("properties") or {}
    return text(props.get("status") or run.get("status")).casefold()


def run_start(run: dict[str, Any]) -> str:
    props = run.get("properties") or {}
    return text(props.get("startTime") or props.get("starttime") or run.get("startTime"))


def run_summary(run: dict[str, Any]) -> dict[str, Any]:
    props = run.get("properties") or {}
    return {
        "id": text(run.get("name") or run.get("id")),
        "status": run_status(run),
        "start_time": run_start(run),
        "end_time": text(props.get("endTime") or props.get("endtime") or run.get("endTime")),
    }


def list_runs(
    client: httpx.Client,
    flow_token: str,
    environment_id_value: str,
    flow_unique_id: str,
) -> list[dict[str, Any]]:
    url = (
        f"{FLOW_API}/environments/{urllib.parse.quote(environment_id_value, safe='')}"
        f"/flows/{urllib.parse.quote(flow_unique_id, safe='')}/runs"
    )
    response = client.get(
        url,
        params={"api-version": FLOW_API_VERSION, "$top": "20"},
        headers={"Authorization": f"Bearer {flow_token}", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return [item for item in response.json().get("value", []) if isinstance(item, dict)]


def wait_for_two_successful_runs(
    client: httpx.Client,
    flow_token: str,
    environment_id_value: str,
    flow_unique_id: str,
    activated_at: datetime,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    observed: dict[str, dict[str, Any]] = {}
    while time.monotonic() < deadline:
        for item in list_runs(client, flow_token, environment_id_value, flow_unique_id):
            started = run_start(item)
            if not started:
                continue
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            except ValueError:
                continue
            if start_dt < activated_at:
                continue
            rid = text(item.get("name") or item.get("id"))
            if rid:
                observed[rid] = item

        terminal = [item for item in observed.values() if run_status(item) in TERMINAL_SUCCESS | TERMINAL_FAILURE]
        failures = [item for item in terminal if run_status(item) in TERMINAL_FAILURE]
        if failures:
            raise E2EError(
                "FLOW_RUN_FAILED:"
                + json.dumps([run_summary(item) for item in failures], ensure_ascii=False)
            )
        successes = sorted(
            [item for item in terminal if run_status(item) in TERMINAL_SUCCESS],
            key=run_start,
        )
        if len(successes) >= 2:
            return successes[:2]
        time.sleep(10)

    raise E2EError(
        "FLOW_RUN_TIMEOUT:"
        + json.dumps([run_summary(item) for item in observed.values()], ensure_ascii=False)
    )


def cleanup_flow(client: httpx.Client, dv_token: str, evidence: dict[str, Any]) -> None:
    flow = find_flow(client, dv_token)
    if flow is None:
        evidence["cleanup"] = {"flow_found": False, "deactivated": True}
        return
    workflow_id = text(flow.get("workflowid"))
    if int(flow.get("statecode", 0)) != 0:
        flow = set_flow_state(client, dv_token, workflow_id, 0)
    evidence["cleanup"] = {
        "flow_found": True,
        "workflow_id": workflow_id,
        "deactivated": int(flow.get("statecode", -1)) == 0,
        "final_statecode": flow.get("statecode"),
    }
    if not evidence["cleanup"]["deactivated"]:
        raise E2EError("FLOW_DEACTIVATION_FAILED")


def self_test() -> None:
    payload = build_clientdata("reqsys_sharedoffice365_test")
    refs = payload["properties"]["connectionReferences"]
    definition = payload["properties"]["definition"]
    actions = definition["actions"]
    if refs[OUTLOOK_CONNECTION_KEY]["connection"]["connectionReferenceLogicalName"] != "reqsys_sharedoffice365_test":
        raise E2EError("SELFTEST_CONNECTION_REFERENCE")
    if actions["Create_event_V4"]["inputs"]["host"]["operationId"] != "V4CalendarPostItem":
        raise E2EError("SELFTEST_CREATE_OPERATION")
    if actions["Get_events_pass2"]["inputs"]["host"]["operationId"] != "V4CalendarGetItems":
        raise E2EError("SELFTEST_GET_OPERATION")
    update = actions["Pass2_require_exactly_one"]["actions"]["Update_event_pass2_evidence"]
    if update["inputs"]["host"]["operationId"] != "V4CalendarPatchItem":
        raise E2EError("SELFTEST_UPDATE_OPERATION")
    raw = json.dumps(payload)
    if IDEMPOTENCY_KEY not in raw or "SecondPassValidated=true" not in raw:
        raise E2EError("SELFTEST_IDEMPOTENCY_MARKERS")
    print("PA_OUTLOOK_E2E_SELFTEST_OK")


def run_apply(args: argparse.Namespace) -> int:
    evidence: dict[str, Any] = {
        "schema": "reqsys-powerautomate-outlook-idempotency-e2e/v2",
        "correlation_id": args.correlation_id,
        "source_sha": args.source_sha,
        "environment": "dev",
        "dataverse_url": DATAVERSE_URL,
        "flow_name": FLOW_NAME,
        "event_subject": EVENT_SUBJECT,
        "event_start_utc": EVENT_START + "Z",
        "event_end_utc": EVENT_END + "Z",
        "idempotency_key": IDEMPOTENCY_KEY,
        "status": "started",
        "production_touched": False,
        "secrets_exposed": False,
        "secret_resolution": {},
        "started_at": now_iso(),
    }
    output = Path(args.evidence_file)

    try:
        validate_runtime_is_dev(evidence)
        for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
            meta = describe_secret_resolution(name)
            evidence["secret_resolution"][name] = {
                "configured": bool(meta.get("configured")),
                "source": meta.get("source"),
                "value_exposed": False,
            }

        with httpx.Client(follow_redirects=True) as client:
            dv_token = token(client, DATAVERSE_URL.rstrip("/") + "/.default")
            flow_token = token(client, "https://service.flow.microsoft.com/.default")

            target = discover_dev_environment(client, flow_token)
            evidence["power_platform_environment"] = {
                "id": target["id"],
                "name": target["name"],
                "sku": target["sku"],
                "url": target["url"],
            }

            ref = discover_outlook_reference(client, dv_token)
            evidence["outlook_connection_reference"] = {
                "logical_name": ref["logical_name"],
                "display_name": ref["display_name"],
                "connector_id": ref["connector_id"],
                "statecode": ref["statecode"],
                "connection_id_sha256": hashlib.sha256(ref["connection_id"].encode("utf-8")).hexdigest(),
            }

            flow, created = upsert_flow(
                client,
                dv_token,
                ref["logical_name"],
                args.correlation_id,
            )
            workflow_id = text(flow.get("workflowid"))
            flow_unique_id = text(flow.get("workflowidunique")) or workflow_id
            evidence["flow"] = {
                "workflow_id": workflow_id,
                "workflow_unique_id": flow_unique_id,
                "created": created,
                "state_before_activation": flow.get("statecode"),
            }

            activated_at = datetime.now(timezone.utc)
            active = set_flow_state(client, dv_token, workflow_id, 1)
            evidence["flow"]["activated_at"] = activated_at.isoformat()
            evidence["flow"]["state_after_activation"] = active.get("statecode")

            try:
                runs = wait_for_two_successful_runs(
                    client,
                    flow_token,
                    target["id"],
                    flow_unique_id,
                    activated_at,
                    args.wait_seconds,
                )
                evidence["runs"] = [run_summary(item) for item in runs]
                evidence["two_successful_runs"] = len(runs) == 2
                evidence["status"] = "power_automate_e2e_succeeded"
            finally:
                cleanup_flow(client, dv_token, evidence)

        if evidence.get("status") != "power_automate_e2e_succeeded":
            raise E2EError("E2E_NOT_SUCCEEDED")
        if not evidence.get("cleanup", {}).get("deactivated"):
            raise E2EError("FLOW_NOT_DEACTIVATED")

        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(json.dumps({
            "status": evidence["status"],
            "flow_name": FLOW_NAME,
            "two_successful_runs": evidence["two_successful_runs"],
            "deactivated": evidence["cleanup"]["deactivated"],
            "production_touched": False,
            "secrets_exposed": False,
        }, ensure_ascii=False))
        return 0

    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = safe_error(exc)
        evidence["completed_at"] = now_iso()
        try:
            with httpx.Client(follow_redirects=True) as client:
                dv_token = token(client, DATAVERSE_URL.rstrip("/") + "/.default")
                cleanup_flow(client, dv_token, evidence)
        except Exception as cleanup_exc:
            evidence["cleanup_error"] = safe_error(cleanup_exc)
        write_json(output, evidence)
        print(json.dumps({
            "status": "failed",
            "error": evidence["error"],
            "cleanup": evidence.get("cleanup"),
            "production_touched": False,
            "secrets_exposed": False,
        }, ensure_ascii=False), file=sys.stderr)
        return 1


def run_deactivate_only(args: argparse.Namespace) -> int:
    evidence: dict[str, Any] = {
        "schema": "reqsys-powerautomate-outlook-idempotency-e2e-cleanup/v1",
        "correlation_id": args.correlation_id,
        "source_sha": args.source_sha,
        "environment": "dev",
        "flow_name": FLOW_NAME,
        "production_touched": False,
        "secrets_exposed": False,
        "started_at": now_iso(),
    }
    output = Path(args.evidence_file)
    try:
        validate_runtime_is_dev(evidence)
        with httpx.Client(follow_redirects=True) as client:
            dv_token = token(client, DATAVERSE_URL.rstrip("/") + "/.default")
            cleanup_flow(client, dv_token, evidence)
        evidence["status"] = "deactivated"
        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(json.dumps({
            "status": "deactivated",
            "cleanup": evidence["cleanup"],
            "production_touched": False,
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        evidence["status"] = "cleanup_failed"
        evidence["error"] = safe_error(exc)
        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(json.dumps({"status": "cleanup_failed", "error": evidence["error"]}, ensure_ascii=False), file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("self-test", "apply", "deactivate-only"), default="self-test")
    parser.add_argument("--correlation-id", default="local-self-test")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--evidence-file", default="/tmp/reqsys-pa-outlook-e2e.json")
    parser.add_argument("--wait-seconds", type=int, default=180)
    args = parser.parse_args()

    if args.mode == "self-test":
        self_test()
        return 0
    if not args.source_sha or len(args.source_sha) != 40:
        raise SystemExit("source_sha_required")
    if args.wait_seconds < 60 or args.wait_seconds > 300:
        raise SystemExit("wait_seconds_out_of_bounds")
    if args.mode == "apply":
        return run_apply(args)
    return run_deactivate_only(args)


if __name__ == "__main__":
    raise SystemExit(main())
