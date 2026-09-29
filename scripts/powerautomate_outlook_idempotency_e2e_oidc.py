#!/usr/bin/env python3
"""E2E OIDC governado: Power Automate -> Outlook em Power Platform DEV."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEV_DATAVERSE_URL = "https://orge9b920f1.crm2.dynamics.com"
GITHUB_ENVIRONMENT = "reqsys-power-platform-dev"
FLOW_NAME = "PA-E2E - Change 1842 Outlook Idempotency 20260928"
EVENT_SUBJECT = "[PA-E2E CHANGE 1842] Revisao pos-aprovacao 20260928"
NEGATIVE_SUBJECT = "[PA-E2E NEGATIVE 1842] Nao deve existir 20260928"
IDEMPOTENCY_KEY = "CHANGE-1842-CALENDAR-REVIEW-PA-E2E-20260928-V1"
EVENT_START = "2026-09-30T14:00:00"
EVENT_END = "2026-09-30T14:30:00"
CONNECTION_KEY = "shared_office365"
API_ID = "/providers/Microsoft.PowerApps/apis/shared_office365"
SUCCESS_STATUSES = {"success", "succeeded"}
FAILURE_STATUSES = {"failed", "cancelled", "canceled", "timedout", "timeout"}


class E2EError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}:{exc}"[:1200]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bearer() -> str:
    value = str(os.getenv("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN") or "").strip()
    if not value:
        raise E2EError("OIDC_DATAVERSE_TOKEN_MISSING")
    return value


def canonical_base(value: str) -> str:
    base = str(value or "").strip().rstrip("/")
    if base.casefold() != DEV_DATAVERSE_URL.casefold():
        raise E2EError("DATAVERSE_TARGET_NOT_CANONICAL_DEV")
    return base


def headers(token: str, *, prefer_representation: bool = False) -> dict[str, str]:
    result = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }
    if prefer_representation:
        result["Prefer"] = "return=representation"
    return result


def openapi_inputs(operation_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": {
            "connectionName": CONNECTION_KEY,
            "operationId": operation_id,
            "apiId": API_ID,
        },
        "parameters": parameters,
        "authentication": "@parameters('$authentication')",
    }


def count_expression(action_name: str, expected: int) -> dict[str, Any]:
    return {
        "and": [
            {"equals": [f"@length(body('{action_name}')?['value'])", expected]}
        ]
    }


def build_clientdata(logical_name: str) -> dict[str, Any]:
    calendar_expr = "@first(body('Get_calendars_V2')?['value'])?['id']"
    event_filter = f"subject eq '{EVENT_SUBJECT}'"
    negative_filter = f"subject eq '{NEGATIVE_SUBJECT}'"

    common = {
        "table": calendar_expr,
        "subject": EVENT_SUBJECT,
        "start": EVENT_START,
        "end": EVENT_END,
        "timeZone": "UTC",
        "showAs": "free",
        "responseRequested": False,
        "isReminderOn": False,
    }
    create_parameters = {
        **common,
        "body": (
            "ReqSys Power Automate E2E.<br>"
            f"IdempotencyKey: {IDEMPOTENCY_KEY}<br>"
            "Pass1Created=true"
        ),
    }
    update_parameters = {
        **common,
        "id": "@variables('EventId')",
        "body": (
            "ReqSys Power Automate E2E.<br>"
            f"IdempotencyKey: {IDEMPOTENCY_KEY}<br>"
            "Pass1CreatedOrReused=true<br>"
            "SecondPassValidated=true"
        ),
    }

    actions: dict[str, Any] = {
        "Get_calendars_V2": {
            "type": "OpenApiConnection",
            "runAfter": {},
            "inputs": openapi_inputs("CalendarGetTables_V2", {}),
        },
        "Get_events_negative_control": {
            "type": "OpenApiConnection",
            "runAfter": {"Get_calendars_V2": ["Succeeded"]},
            "inputs": openapi_inputs(
                "V4CalendarGetItems",
                {"table": calendar_expr, "$filter": negative_filter, "$top": 10},
            ),
        },
        "Negative_control_must_be_zero": {
            "type": "If",
            "runAfter": {"Get_events_negative_control": ["Succeeded"]},
            "expression": count_expression("Get_events_negative_control", 0),
            "actions": {},
            "else": {
                "actions": {
                    "Fail_negative_control": {
                        "type": "Terminate",
                        "runAfter": {},
                        "inputs": {
                            "runStatus": "Failed",
                            "runError": {
                                "code": "NEGATIVE_CONTROL_FAILED",
                                "message": "Negative control subject unexpectedly exists.",
                            },
                        },
                    }
                }
            },
        },
        "Init_EventId": {
            "type": "InitializeVariable",
            "runAfter": {"Negative_control_must_be_zero": ["Succeeded"]},
            "inputs": {
                "variables": [{"name": "EventId", "type": "string", "value": ""}]
            },
        },
        "Get_events_pass1": {
            "type": "OpenApiConnection",
            "runAfter": {"Init_EventId": ["Succeeded"]},
            "inputs": openapi_inputs(
                "V4CalendarGetItems",
                {"table": calendar_expr, "$filter": event_filter, "$top": 10},
            ),
        },
        "Pass1_create_if_missing": {
            "type": "If",
            "runAfter": {"Get_events_pass1": ["Succeeded"]},
            "expression": count_expression("Get_events_pass1", 0),
            "actions": {
                "Create_event_V4": {
                    "type": "OpenApiConnection",
                    "runAfter": {},
                    "inputs": openapi_inputs("V4CalendarPostItem", create_parameters),
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
            "inputs": openapi_inputs(
                "V4CalendarGetItems",
                {"table": calendar_expr, "$filter": event_filter, "$top": 10},
            ),
        },
        "Pass2_require_exactly_one": {
            "type": "If",
            "runAfter": {"Get_events_pass2": ["Succeeded"]},
            "expression": count_expression("Get_events_pass2", 1),
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
                    "inputs": openapi_inputs(
                        "V4CalendarPatchItem", update_parameters
                    ),
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
                "negativeControlPassed": True,
                "secondPassValidated": True,
            },
        },
    }

    return {
        "properties": {
            "connectionReferences": {
                CONNECTION_KEY: {
                    "runtimeSource": "embedded",
                    "connection": {
                        "connectionReferenceLogicalName": logical_name
                    },
                    "api": {"name": CONNECTION_KEY},
                }
            },
            "definition": {
                "$schema": (
                    "https://schema.management.azure.com/providers/Microsoft.Logic/"
                    "schemas/2016-06-01/workflowdefinition.json#"
                ),
                "contentVersion": "1.0.0.0",
                "parameters": {
                    "$connections": {"defaultValue": {}, "type": "Object"},
                    "$authentication": {
                        "defaultValue": {},
                        "type": "SecureObject",
                    },
                },
                "triggers": {
                    "Recurrence": {
                        "type": "Recurrence",
                        "recurrence": {
                            "frequency": "Minute",
                            "interval": 1,
                        },
                    }
                },
                "actions": actions,
                "outputs": {},
            },
            "templateName": None,
        },
        "schemaVersion": "1.0.0.0",
    }


def self_test() -> None:
    payload = build_clientdata("reqsys_sharedoffice365_test")
    actions = payload["properties"]["definition"]["actions"]
    assert (
        actions["Create_event_V4"]["inputs"]["host"]["operationId"]
        == "V4CalendarPostItem"
    )
    assert (
        actions["Get_events_pass2"]["inputs"]["host"]["operationId"]
        == "V4CalendarGetItems"
    )
    update = actions["Pass2_require_exactly_one"]["actions"][
        "Update_event_pass2_evidence"
    ]
    assert update["inputs"]["host"]["operationId"] == "V4CalendarPatchItem"
    raw = json.dumps(payload, ensure_ascii=False)
    assert IDEMPOTENCY_KEY in raw
    assert "SecondPassValidated=true" in raw
    assert NEGATIVE_SUBJECT in raw
    print("POWER_AUTOMATE_OUTLOOK_OIDC_SELFTEST_OK")


def get_json(
    client: httpx.Client,
    url: str,
    token: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = client.get(
        url,
        headers=headers(token),
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise E2EError("DATAVERSE_RESPONSE_NOT_OBJECT")
    return data


def find_outlook_reference(
    client: httpx.Client,
    base: str,
    token: str,
) -> dict[str, Any]:
    data = get_json(
        client,
        f"{base}/api/data/v9.2/connectionreferences",
        token,
        params={
            "$select": (
                "connectionreferenceid,connectionreferencelogicalname,"
                "connectionid,connectorid,displayname,statecode"
            )
        },
    )
    refs = []
    for item in data.get("value", []):
        connector = str(item.get("connectorid") or "").casefold()
        logical = str(
            item.get("connectionreferencelogicalname") or ""
        ).strip()
        connection_id = str(item.get("connectionid") or "").strip()
        if "/shared_office365" in connector and logical and connection_id:
            refs.append(item)
    if len(refs) != 1:
        raise E2EError(
            f"OUTLOOK_CONNECTION_REFERENCE_AMBIGUOUS:{len(refs)}"
        )
    return refs[0]


def find_flow(
    client: httpx.Client,
    base: str,
    token: str,
) -> dict[str, Any] | None:
    data = get_json(
        client,
        f"{base}/api/data/v9.2/workflows",
        token,
        params={
            "$filter": f"name eq '{FLOW_NAME}' and category eq 5",
            "$select": (
                "workflowid,workflowidunique,name,statecode,statuscode,"
                "modifiedon,clientdata"
            ),
            "$top": "2",
        },
    )
    rows = list(data.get("value") or [])
    if len(rows) > 1:
        raise E2EError(f"FLOW_NAME_AMBIGUOUS:{len(rows)}")
    return rows[0] if rows else None


def read_flow(
    client: httpx.Client,
    base: str,
    token: str,
    workflow_id: str,
) -> dict[str, Any]:
    return get_json(
        client,
        f"{base}/api/data/v9.2/workflows({workflow_id})",
        token,
        params={
            "$select": (
                "workflowid,workflowidunique,name,statecode,statuscode,"
                "modifiedon"
            )
        },
    )


def set_state(
    client: httpx.Client,
    base: str,
    token: str,
    workflow_id: str,
    *,
    active: bool,
) -> dict[str, Any]:
    payload = (
        {"statecode": 1, "statuscode": 2}
        if active
        else {"statecode": 0, "statuscode": 1}
    )
    response = client.patch(
        f"{base}/api/data/v9.2/workflows({workflow_id})",
        headers={**headers(token), "If-Match": "*"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    current = read_flow(client, base, token, workflow_id)
    expected = 1 if active else 0
    if int(current.get("statecode", -1)) != expected:
        raise E2EError(
            f"FLOW_STATE_READBACK_MISMATCH:"
            f"{current.get('statecode')}!={expected}"
        )
    return current


def upsert_flow(
    client: httpx.Client,
    base: str,
    token: str,
    logical_name: str,
    correlation_id: str,
) -> tuple[dict[str, Any], bool]:
    flow = find_flow(client, base, token)
    created = flow is None
    clientdata = json.dumps(
        build_clientdata(logical_name),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    if flow is None:
        response = client.post(
            f"{base}/api/data/v9.2/workflows",
            headers=headers(token, prefer_representation=True),
            json={
                "category": 5,
                "name": FLOW_NAME,
                "type": 1,
                "description": (
                    f"Governed DEV E2E. correlation_id={correlation_id}"
                ),
                "primaryentity": "none",
                "clientdata": clientdata,
            },
            timeout=45,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}
        workflow_id = str(body.get("workflowid") or "").strip()
        if not workflow_id:
            entity = str(
                response.headers.get("OData-EntityId")
                or response.headers.get("odata-entityid")
                or ""
            )
            marker = "workflows("
            if marker in entity:
                workflow_id = entity.split(marker, 1)[1].split(")", 1)[0]
        if not workflow_id:
            raise E2EError("CREATED_FLOW_ID_MISSING")
        flow = read_flow(client, base, token, workflow_id)
    else:
        workflow_id = str(flow.get("workflowid") or "")
        if int(flow.get("statecode", 0)) == 1:
            set_state(
                client,
                base,
                token,
                workflow_id,
                active=False,
            )
        response = client.patch(
            f"{base}/api/data/v9.2/workflows({workflow_id})",
            headers={**headers(token), "If-Match": "*"},
            json={
                "clientdata": clientdata,
                "description": (
                    f"Governed DEV E2E. correlation_id={correlation_id}"
                ),
            },
            timeout=45,
        )
        response.raise_for_status()
        flow = read_flow(client, base, token, workflow_id)

    return flow, created


def normalize_guid(value: Any) -> str:
    return str(value or "").strip().strip("{}").casefold()


def flowrun_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("flowrunid") or item.get("name") or ""),
        "status": str(item.get("status") or ""),
        "start_time": str(item.get("starttime") or ""),
        "end_time": str(item.get("endtime") or ""),
        "error_code": str(item.get("errorcode") or ""),
    }


def list_flowruns(
    client: httpx.Client,
    base: str,
    token: str,
    workflow_id: str,
    activated_at: datetime,
) -> list[dict[str, Any]]:
    data = get_json(
        client,
        f"{base}/api/data/v9.2/flowruns",
        token,
        params={
            "$select": (
                "flowrunid,name,starttime,endtime,status,errorcode,"
                "errormessage,_workflow_value"
            ),
            "$filter": f"_workflow_value eq {workflow_id}",
            "$orderby": "starttime desc",
            "$top": "20",
        },
    )
    result = []
    for item in data.get("value", []):
        if normalize_guid(item.get("_workflow_value")) != normalize_guid(
            workflow_id
        ):
            continue
        raw = str(item.get("starttime") or "")
        try:
            started = datetime.fromisoformat(
                raw.replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if started >= activated_at:
            result.append(item)
    return sorted(
        result,
        key=lambda row: str(row.get("starttime") or ""),
    )


def wait_for_two_successful_runs(
    client: httpx.Client,
    base: str,
    token: str,
    workflow_id: str,
    activated_at: datetime,
    wait_seconds: int,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + wait_seconds
    last: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        last = list_flowruns(
            client,
            base,
            token,
            workflow_id,
            activated_at,
        )
        terminal = [
            item
            for item in last
            if str(item.get("status") or "").casefold()
            in SUCCESS_STATUSES | FAILURE_STATUSES
        ]
        failures = [
            item
            for item in terminal
            if str(item.get("status") or "").casefold()
            in FAILURE_STATUSES
        ]
        if failures:
            raise E2EError(
                "FLOW_RUN_FAILED:"
                + json.dumps(
                    [flowrun_summary(item) for item in failures],
                    ensure_ascii=False,
                )
            )
        successes = [
            item
            for item in terminal
            if str(item.get("status") or "").casefold()
            in SUCCESS_STATUSES
        ]
        if len(successes) >= 2:
            return successes[:2]
        time.sleep(10)

    raise E2EError(
        "FLOW_RUN_TIMEOUT:"
        + json.dumps(
            [flowrun_summary(item) for item in last],
            ensure_ascii=False,
        )
    )


def cleanup(
    client: httpx.Client,
    base: str,
    token: str,
    evidence: dict[str, Any],
) -> None:
    flow = find_flow(client, base, token)
    if flow is None:
        evidence["cleanup"] = {
            "flow_found": False,
            "deactivated": True,
        }
        return

    workflow_id = str(flow.get("workflowid") or "")
    if int(flow.get("statecode", 0)) != 0:
        flow = set_state(
            client,
            base,
            token,
            workflow_id,
            active=False,
        )

    evidence["cleanup"] = {
        "flow_found": True,
        "workflow_id": workflow_id,
        "deactivated": int(flow.get("statecode", -1)) == 0,
        "final_statecode": flow.get("statecode"),
    }
    if not evidence["cleanup"]["deactivated"]:
        raise E2EError("FLOW_DEACTIVATION_NOT_CONFIRMED")


def run_apply(args: argparse.Namespace) -> int:
    base = canonical_base(args.dataverse_url)
    token = bearer()
    evidence: dict[str, Any] = {
        "schema": "powerautomate-outlook-idempotency-oidc/v1",
        "status": "started",
        "github_environment": GITHUB_ENVIRONMENT,
        "environment": "dev",
        "dataverse_url": base,
        "source_sha": args.source_sha,
        "correlation_id": args.correlation_id,
        "auth_mode": "github_oidc",
        "static_client_secret_used": False,
        "token_persisted": False,
        "production_touched": False,
        "flow_name": FLOW_NAME,
        "event_subject": EVENT_SUBJECT,
        "negative_subject": NEGATIVE_SUBJECT,
        "idempotency_key": IDEMPOTENCY_KEY,
        "started_at": now_iso(),
    }
    output = Path(args.output)

    try:
        with httpx.Client(follow_redirects=True) as client:
            ref = find_outlook_reference(
                client,
                base,
                token,
            )
            evidence["connection_reference"] = {
                "logical_name": str(
                    ref.get("connectionreferencelogicalname") or ""
                ),
                "display_name": str(ref.get("displayname") or ""),
                "connector_id": str(ref.get("connectorid") or ""),
                "bound": bool(ref.get("connectionid")),
            }

            flow, created = upsert_flow(
                client,
                base,
                token,
                evidence["connection_reference"]["logical_name"],
                args.correlation_id,
            )
            workflow_id = str(flow.get("workflowid") or "")
            evidence["flow"] = {
                "workflow_id": workflow_id,
                "workflow_unique_id": str(
                    flow.get("workflowidunique") or ""
                ),
                "created": created,
                "pre_activation_statecode": flow.get("statecode"),
            }

            activated_at = datetime.now(timezone.utc)
            active = set_state(
                client,
                base,
                token,
                workflow_id,
                active=True,
            )
            evidence["flow"]["activation_readback_statecode"] = (
                active.get("statecode")
            )
            evidence["flow"]["activated_at"] = (
                activated_at.isoformat()
            )

            try:
                runs = wait_for_two_successful_runs(
                    client,
                    base,
                    token,
                    workflow_id,
                    activated_at,
                    args.wait_seconds,
                )
                evidence["runs"] = [
                    flowrun_summary(item) for item in runs
                ]
                evidence["two_successful_runs"] = True
                evidence["status"] = "power_automate_runs_succeeded"
            finally:
                cleanup(
                    client,
                    base,
                    token,
                    evidence,
                )

        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(
            json.dumps(
                {
                    "status": evidence["status"],
                    "two_successful_runs": evidence.get(
                        "two_successful_runs", False
                    ),
                    "deactivated": evidence.get(
                        "cleanup", {}
                    ).get("deactivated", False),
                    "auth_mode": "github_oidc",
                    "production_touched": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = safe_error(exc)
        try:
            with httpx.Client(follow_redirects=True) as client:
                cleanup(
                    client,
                    base,
                    token,
                    evidence,
                )
        except Exception as cleanup_exc:
            evidence["cleanup_error"] = safe_error(cleanup_exc)
        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": evidence["error"],
                    "cleanup": evidence.get("cleanup"),
                    "production_touched": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


def run_cleanup(args: argparse.Namespace) -> int:
    base = canonical_base(args.dataverse_url)
    token = bearer()
    evidence: dict[str, Any] = {
        "schema": "powerautomate-outlook-idempotency-oidc-cleanup/v1",
        "github_environment": GITHUB_ENVIRONMENT,
        "environment": "dev",
        "dataverse_url": base,
        "source_sha": args.source_sha,
        "correlation_id": args.correlation_id,
        "auth_mode": "github_oidc",
        "static_client_secret_used": False,
        "production_touched": False,
        "started_at": now_iso(),
    }
    output = Path(args.output)

    try:
        with httpx.Client(follow_redirects=True) as client:
            cleanup(
                client,
                base,
                token,
                evidence,
            )
        evidence["status"] = "deactivated"
        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(
            json.dumps(
                {
                    "status": "deactivated",
                    "cleanup": evidence["cleanup"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        evidence["status"] = "cleanup_failed"
        evidence["error"] = safe_error(exc)
        evidence["completed_at"] = now_iso()
        write_json(output, evidence)
        print(
            json.dumps(
                {
                    "status": "cleanup_failed",
                    "error": evidence["error"],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("self-test", "apply", "deactivate-only"),
        default="self-test",
    )
    parser.add_argument(
        "--dataverse-url",
        default=DEV_DATAVERSE_URL,
    )
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--correlation-id", default="local")
    parser.add_argument(
        "--output",
        default="audit/powerautomate-outlook/evidence.json",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
    )
    args = parser.parse_args()

    if args.mode == "self-test":
        self_test()
        return 0

    if len(args.source_sha) != 40:
        raise SystemExit("source_sha_required")
    if not 120 <= args.wait_seconds <= 300:
        raise SystemExit("wait_seconds_out_of_bounds")

    if args.mode == "apply":
        return run_apply(args)
    return run_cleanup(args)


if __name__ == "__main__":
    raise SystemExit(main())
