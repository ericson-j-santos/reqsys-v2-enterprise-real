#!/usr/bin/env python3
"""Read-only probe for an existing Outlook/Office 365 connection reference in Power Platform DEV."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def _token(tenant: str, client: str, secret: str, env_url: str) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client,
        "client_secret": secret,
        "scope": env_url.rstrip("/") + "/.default",
    }).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())["access_token"]


def _is_outlook_ref(item: dict) -> bool:
    text = " ".join(str(item.get(k) or "") for k in (
        "connectorid", "connectionreferencelogicalname", "displayname"
    )).casefold()
    return "office365" in text or "outlook" in text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-file", required=True)
    ap.add_argument("--correlation-id", required=True)
    args = ap.parse_args()

    tenant = os.environ.get("POWERPLATFORM_TENANT_ID", "").strip()
    client = os.environ.get("POWERPLATFORM_APP_ID", "").strip()
    secret = os.environ.get("POWERPLATFORM_CLIENT_SECRET", "").strip()
    env_url = os.environ.get("DEV_ENVIRONMENT_URL", "").strip().rstrip("/")

    evidence = {
        "schema": "reqsys-powerplatform-outlook-probe/v1",
        "correlation_id": args.correlation_id,
        "environment": "dev",
        "configuration_complete": bool(tenant and client and secret and env_url),
        "secret_value_exposed": False,
        "production_touched": False,
        "read_only": True,
        "outlook_connection_reference_count": 0,
        "connection_references": [],
        "usable_reference_found": False,
    }

    out = Path(args.evidence_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not evidence["configuration_complete"]:
        out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print("POWERPLATFORM_OUTLOOK_PROBE_BLOCKED configuration_complete=false")
        return 2

    bearer = _token(tenant, client, secret, env_url)
    query = urllib.parse.urlencode({
        "$select": "connectionreferencelogicalname,connectionid,connectorid,displayname,statecode"
    })
    req = urllib.request.Request(
        f"{env_url}/api/data/v9.2/connectionreferences?{query}",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())

    matches = []
    for item in payload.get("value", []):
        if not _is_outlook_ref(item):
            continue
        connection_id = str(item.get("connectionid") or "")
        matches.append({
            "logical_name": str(item.get("connectionreferencelogicalname") or ""),
            "display_name": str(item.get("displayname") or ""),
            "connector_id": str(item.get("connectorid") or ""),
            "statecode": item.get("statecode"),
            "has_connection_id": bool(connection_id),
            "connection_id_sha256": (
                hashlib.sha256(connection_id.encode()).hexdigest() if connection_id else None
            ),
        })

    evidence["outlook_connection_reference_count"] = len(matches)
    evidence["connection_references"] = matches
    evidence["usable_reference_found"] = any(
        x["has_connection_id"] and x["logical_name"] for x in matches
    )
    out.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("POWERPLATFORM_OUTLOOK_PROBE_OK")
    print(f"outlook_connection_reference_count={len(matches)}")
    print(f"usable_reference_found={str(evidence['usable_reference_found']).lower()}")
    print("secret_value_exposed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
