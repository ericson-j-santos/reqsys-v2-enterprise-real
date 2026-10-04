#!/usr/bin/env python3
"""Probe read-only da identidade OIDC governada contra Fabric, Power BI e Graph."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_TENANT = "6d09c88c-0617-490c-8329-305e577684bc"


class ProbeError(RuntimeError):
    pass


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
        raise ProbeError(f"azure_cli_failed:{args[0] if args else 'unknown'}")
    return (result.stdout or "").strip()


def _token(resource: str) -> str:
    token = _az_tsv(
        [
            "account",
            "get-access-token",
            "--resource",
            resource,
            "--query",
            "accessToken",
            "--output",
            "tsv",
            "--only-show-errors",
        ]
    )
    if not token:
        raise ProbeError("access_token_empty")
    return token


def _get_json(url: str, bearer: str) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {bearer}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return response.status, payload if isinstance(payload, dict) else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return 0, {}


def _probe_api(
    evidence: dict[str, Any],
    key: str,
    *,
    resource: str,
    url: str,
    list_key: str = "value",
) -> None:
    try:
        bearer = _token(resource)
        evidence[key]["token_obtained"] = True
        status, payload = _get_json(url, bearer)
        evidence[key]["status"] = status
        if status == 200:
            values = payload.get(list_key, payload.get("value", []))
            evidence[key]["raw_count"] = len(values) if isinstance(values, list) else 0
            evidence[key]["payload"] = payload
    except ProbeError as exc:
        evidence[key]["error_code"] = str(exc).split(":", 1)[0]


def run_probe(*, tenant_id: str, client_id: str, output: Path) -> dict[str, Any]:
    tenant_id = tenant_id.strip()
    client_id = client_id.strip()
    if not tenant_id or not client_id:
        raise ProbeError("oidc_configuration_missing")

    active_tenant = _az_tsv(["account", "show", "--query", "tenantId", "--output", "tsv"])
    evidence: dict[str, Any] = {
        "schema": "fabric-oidc-readonly-probe/v1",
        "status": "started",
        "environment": "development",
        "tenant_match": active_tenant.casefold() == tenant_id.casefold() == EXPECTED_TENANT.casefold(),
        "oidc_client_id": client_id,
        "secret_value_exposed": False,
        "mutations_performed": False,
        "fabric": {"token_obtained": False, "status": None, "workspaces": []},
        "fabric_admin": {"token_obtained": False, "status": None, "workspaces": []},
        "powerbi": {"token_obtained": False, "status": None, "workspaces": []},
        "graph": {"token_obtained": False, "status": None, "apps": [], "oidc_app": []},
    }

    _probe_api(
        evidence,
        "fabric",
        resource="https://api.fabric.microsoft.com",
        url="https://api.fabric.microsoft.com/v1/workspaces",
    )
    if evidence["fabric"].get("status") == 200:
        values = evidence["fabric"].pop("payload", {}).get("value", [])
        evidence["fabric"]["workspaces"] = [
            {
                "id": str(item.get("id") or ""),
                "displayName": str(item.get("displayName") or ""),
                "type": str(item.get("type") or ""),
            }
            for item in values
            if isinstance(item, dict)
        ]
    else:
        evidence["fabric"].pop("payload", None)

    _probe_api(
        evidence,
        "fabric_admin",
        resource="https://api.fabric.microsoft.com",
        url="https://api.fabric.microsoft.com/v1/admin/workspaces",
    )
    if evidence["fabric_admin"].get("status") == 200:
        payload = evidence["fabric_admin"].pop("payload", {})
        values = payload.get("workspaces", payload.get("value", []))
        evidence["fabric_admin"]["workspaces"] = [
            {
                "id": str(item.get("id") or ""),
                "displayName": str(item.get("displayName") or ""),
                "state": str(item.get("state") or ""),
                "type": str(item.get("type") or ""),
            }
            for item in values
            if isinstance(item, dict)
        ]
    else:
        evidence["fabric_admin"].pop("payload", None)

    _probe_api(
        evidence,
        "powerbi",
        resource="https://analysis.windows.net/powerbi/api",
        url="https://api.powerbi.com/v1.0/myorg/groups",
    )
    if evidence["powerbi"].get("status") == 200:
        values = evidence["powerbi"].pop("payload", {}).get("value", [])
        evidence["powerbi"]["workspaces"] = [
            {"id": str(item.get("id") or ""), "name": str(item.get("name") or "")}
            for item in values
            if isinstance(item, dict)
        ]
    else:
        evidence["powerbi"].pop("payload", None)

    try:
        graph_token = _token("https://graph.microsoft.com")
        evidence["graph"]["token_obtained"] = True

        query = urllib.parse.urlencode(
            {
                "$filter": "displayName eq 'ReqSys ALM Pipeline'",
                "$select": "id,appId,displayName",
            }
        )
        status, payload = _get_json(
            f"https://graph.microsoft.com/v1.0/applications?{query}",
            graph_token,
        )
        evidence["graph"]["status"] = status
        if status == 200:
            evidence["graph"]["apps"] = [
                {
                    "id": str(item.get("id") or ""),
                    "appId": str(item.get("appId") or ""),
                    "displayName": str(item.get("displayName") or ""),
                }
                for item in payload.get("value", [])
                if isinstance(item, dict)
            ]

        self_query = urllib.parse.urlencode(
            {
                "$filter": f"appId eq '{client_id}'",
                "$select": "id,appId,displayName",
            }
        )
        self_status, self_payload = _get_json(
            f"https://graph.microsoft.com/v1.0/applications?{self_query}",
            graph_token,
        )
        evidence["graph"]["oidc_app_status"] = self_status
        if self_status == 200:
            evidence["graph"]["oidc_app"] = [
                {
                    "id": str(item.get("id") or ""),
                    "appId": str(item.get("appId") or ""),
                    "displayName": str(item.get("displayName") or ""),
                }
                for item in self_payload.get("value", [])
                if isinstance(item, dict)
            ]
    except ProbeError as exc:
        evidence["graph"]["error_code"] = str(exc).split(":", 1)[0]

    workspace_map: dict[str, str] = {}
    for item in evidence["fabric"]["workspaces"]:
        if item["id"]:
            workspace_map[item["id"]] = item["displayName"]
    for item in evidence["fabric_admin"]["workspaces"]:
        if item["id"]:
            workspace_map.setdefault(item["id"], item["displayName"])
    for item in evidence["powerbi"]["workspaces"]:
        if item["id"]:
            workspace_map.setdefault(item["id"], item["name"])

    evidence["candidate_workspaces"] = [
        {"id": workspace_id, "name": name}
        for workspace_id, name in sorted(workspace_map.items())
    ]
    evidence["status"] = "completed"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        evidence = run_probe(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            output=args.output,
        )
    except (ProbeError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "schema": "fabric-oidc-readonly-probe/v1",
            "status": "blocked",
            "blocker": type(exc).__name__,
            "secret_value_exposed": False,
            "mutations_performed": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, sort_keys=True))
        return 2

    print("FABRIC_OIDC_PROBE_OK")
    print(f"tenant_match={str(evidence['tenant_match']).lower()}")
    print(f"oidc_client_id={evidence['oidc_client_id']}")
    print(f"fabric_status={evidence['fabric']['status']}")
    print(f"fabric_workspace_count={len(evidence['fabric']['workspaces'])}")
    print(f"fabric_admin_status={evidence['fabric_admin']['status']}")
    print(f"fabric_admin_workspace_count={len(evidence['fabric_admin']['workspaces'])}")
    print(f"powerbi_status={evidence['powerbi']['status']}")
    print(f"powerbi_workspace_count={len(evidence['powerbi']['workspaces'])}")
    print(f"graph_status={evidence['graph']['status']}")
    print(f"graph_app_count={len(evidence['graph']['apps'])}")
    print(f"oidc_app_status={evidence['graph'].get('oidc_app_status')}")
    for item in evidence["candidate_workspaces"]:
        print(f"workspace={item['name']}|{item['id']}")
    for item in evidence["graph"]["apps"]:
        print(f"graph_app={item['displayName']}|{item['appId']}")
    for item in evidence["graph"]["oidc_app"]:
        print(f"oidc_app={item['displayName']}|{item['appId']}")
    print("secret_value_exposed=false")
    print("mutations_performed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
