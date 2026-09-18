#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FLOW_NAMES = (
    "ReqSys - Notificar Teams (Tarefa criada no Planner)",
    "ReqSys - Notificar Teams (Tarefa concluída no Planner)",
)
REQUIRED_CONNECTIONS = {"shared_planner", "shared_teams"}


class FlowStateError(RuntimeError):
    pass


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
        headers["If-Match"] = "*"
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


def connection_keys(row: dict[str, Any]) -> list[str]:
    raw = str(row.get("clientdata") or "")
    try:
        clientdata = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FlowStateError("flow_clientdata_invalido") from exc
    props = clientdata.get("properties") if isinstance(clientdata, dict) else {}
    refs = props.get("connectionReferences") if isinstance(props, dict) else {}
    if not isinstance(refs, dict):
        raise FlowStateError("flow_connection_references_ausentes")
    keys = sorted(str(key) for key in refs)
    missing = sorted(REQUIRED_CONNECTIONS - set(keys))
    if missing:
        raise FlowStateError("flow_connection_references_incompletas:" + ",".join(missing))
    return keys


def workflow_url(base: str, workflow_id: str) -> str:
    return f"{base.rstrip('/')}/api/data/v9.2/workflows({workflow_id})"


def discover(base: str, token: str, name: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "$select": "workflowid,name,statecode,statuscode,category,type,clientdata",
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
        workflow_url(base, workflow_id)
        + "?$select=workflowid,name,statecode,statuscode,category,type,clientdata",
        token,
    )
    if status != 200:
        raise FlowStateError(f"dataverse_get_http_{status}")
    return payload


def activate(base: str, token: str, workflow_id: str) -> None:
    status, payload = request_json(
        "PATCH",
        workflow_url(base, workflow_id),
        token,
        {"statecode": 1, "statuscode": 2},
    )
    if status != 204:
        code = str(((payload.get("error") or {}).get("code") or ""))[:120]
        raise FlowStateError(f"dataverse_activate_http_{status}:{code}")


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
        description="Garante flows Planner→Teams DEV ativos via OIDC/Dataverse"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    base = required("PLANNER_TEAMS_DATAVERSE_URL")
    token = required("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN")
    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "auth_mode": "github_oidc_dataverse",
        "status": "running",
        "flows": [],
        "error": None,
    }

    try:
        for name in FLOW_NAMES:
            before = discover(base, token, name)
            refs = connection_keys(before)
            raw_before = str(before.get("clientdata") or "")
            after = ensure_active(base, token, before)
            raw_after = str(after.get("clientdata") or "")
            before_hash = hashlib.sha256(raw_before.encode()).hexdigest()
            after_hash = hashlib.sha256(raw_after.encode()).hexdigest()
            if before_hash != after_hash:
                raise FlowStateError(f"flow_clientdata_mudou_ao_ativar:{name}")
            evidence["flows"].append(
                {
                    "workflowid": after.get("workflowid"),
                    "name": after.get("name"),
                    "state_before": before.get("statecode"),
                    "status_before": before.get("statuscode"),
                    "state_after": after.get("statecode"),
                    "status_after": after.get("statuscode"),
                    "connection_reference_keys": refs,
                    "clientdata_sha256": after_hash,
                    "clientdata_preserved": True,
                }
            )
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = {
            "type": exc.__class__.__name__,
            "message": str(exc)[:500],
        }

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
