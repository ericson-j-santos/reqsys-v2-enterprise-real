#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from scripts.integration_excel_sql_sharepoint_dataverse import normalize_dataverse_url
from scripts.integration_excel_sql_sharepoint_discovery import (
    discover_sharepoint,
    profile_contract,
)

TIMEOUT = 30.0
DEFAULT_FLOW_NAME = "ReqSys - Excel SQL SharePoint DEV E2E"


class OidcDiscoveryError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def select_flow(items: list[dict[str, Any]], display_name: str) -> dict[str, Any]:
    matches = [
        item
        for item in items
        if text(item.get("name")) == display_name
        and int(item.get("category", -1)) == 5
        and int(item.get("type", -1)) == 1
    ]
    if len(matches) != 1:
        raise OidcDiscoveryError(f"dataverse_flow_alvo_ambiguo:{len(matches)}")
    return matches[0]


def discover_flow(
    client: httpx.Client,
    dataverse_url: str,
    token: str,
    display_name: str,
) -> dict[str, str]:
    safe_name = display_name.replace("'", "''")
    response = client.get(
        f"{normalize_dataverse_url(dataverse_url)}/api/data/v9.2/workflows",
        params={
            "$select": "workflowid,name,statecode,statuscode,category,type",
            "$filter": f"category eq 5 and type eq 1 and name eq '{safe_name}'",
        },
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    item = select_flow(response.json().get("value") or [], display_name)
    return {
        "flow_id": text(item.get("workflowid")),
        "flow_name": text(item.get("name")),
        "statecode": str(item.get("statecode")),
    }


def write_github_env(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for name, value in values.items():
            if "\n" in value or "\r" in value:
                raise OidcDiscoveryError(f"valor_multilinha:{name}")
            handle.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Descoberta E2E DEV via Graph + Dataverse OIDC")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--github-env", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()

    graph_token = text(os.getenv("POWER_PLATFORM_GRAPH_ACCESS_TOKEN"))
    dataverse_token = text(os.getenv("POWER_PLATFORM_DATAVERSE_ACCESS_TOKEN"))
    dataverse_url = text(os.getenv("INTEGRATION_E2E_DATAVERSE_URL"))
    flow_name = text(os.getenv("INTEGRATION_E2E_FLOW_DISPLAY_NAME")) or DEFAULT_FLOW_NAME
    if not graph_token:
        raise OidcDiscoveryError("graph_oidc_token_ausente")
    if not dataverse_token:
        raise OidcDiscoveryError("dataverse_oidc_token_ausente")
    if not dataverse_url:
        raise OidcDiscoveryError("dataverse_url_ausente")

    contract = profile_contract()
    with httpx.Client(follow_redirects=True) as client:
        sp = discover_sharepoint(client, graph_token, contract)
        flow = discover_flow(client, dataverse_url, dataverse_token, flow_name)

    resolved = {
        "INTEGRATION_E2E_DRIVE_ID": sp["drive_id"],
        "INTEGRATION_E2E_FILE_ID": sp["file_id"],
        "INTEGRATION_E2E_SITE_ID": sp["site_id"],
        "INTEGRATION_E2E_LIST_ID": sp["list_id"],
        "INTEGRATION_E2E_SQL_PROCEDURE": contract["procedure"],
        "INTEGRATION_E2E_FLOW_ID": flow["flow_id"],
    }
    write_github_env(args.github_env, resolved)

    evidence = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_oidc_discovery",
        "environment": "dev",
        "source_sha": args.source_sha,
        "correlation_id": args.correlation_id,
        "status": "resolved_non_secret",
        "auth_mode": "oidc_dataverse",
        "resolved_variable_names": sorted(resolved),
        "value_hashes": {name: digest(value) for name, value in resolved.items()},
        "sharepoint_site_name": sp["site_name"],
        "sharepoint_list_name": sp["list_name"],
        "excel_drive_name": sp["drive_name"],
        "excel_file_name": sp["file_name"],
        "flow_name": flow["flow_name"],
        "flow_initial_statecode": flow["statecode"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": evidence["status"],
        "auth_mode": evidence["auth_mode"],
        "resolved_variable_names": evidence["resolved_variable_names"],
        "flow_initial_statecode": flow["statecode"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
