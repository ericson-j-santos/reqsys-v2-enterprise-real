#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRAPH = "https://graph.microsoft.com/v1.0"
RSC_PERMISSION = "ChannelMessage.Read.Group"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def env(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default)).strip()


def required(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"variavel_obrigatoria_ausente:{name}")
    return value


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    request_headers = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:1000]}
        return int(exc.code), payload


def graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    status, payload = http_json(
        "POST",
        f"https://login.microsoftonline.com/{urllib.parse.quote(tenant_id)}/oauth2/v2.0/token",
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
    )
    token = str(payload.get("access_token") or "")
    if status != 200 or not token:
        raise RuntimeError(f"graph_token_failed:http_{status}")
    return token


def graph_call(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return http_json(
        method,
        f"{GRAPH}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        body=body,
    )


def probe_channel(token: str, team_id: str, channel_id: str) -> tuple[str, int]:
    status, _ = graph_call(
        "GET",
        f"/teams/{urllib.parse.quote(team_id)}/channels/{urllib.parse.quote(channel_id)}/messages?$top=1",
        token,
    )
    if status == 200:
        return "ready", status
    if status == 403:
        return "permission_pending", status
    return "probe_failed", status


def install_with_rsc(token: str, team_id: str, catalog_app_id: str) -> tuple[str, int]:
    body = {
        "teamsApp@odata.bind": f"{GRAPH}/appCatalogs/teamsApps/{catalog_app_id}",
        "consentedPermissionSet": {
            "resourceSpecificPermissions": [
                {"permissionValue": RSC_PERMISSION, "permissionType": "application"}
            ]
        },
    }
    status, _ = graph_call(
        "POST",
        f"/teams/{urllib.parse.quote(team_id)}/installedApps",
        token,
        body,
    )
    if status in {200, 201, 204}:
        return "applied", status
    if status == 409:
        return "already_installed_or_conflict", status
    if status in {401, 403}:
        return "bootstrap_permission_required", status
    return "apply_failed", status


def state_signature(payload: dict[str, Any]) -> str:
    material = "|".join(
        str(payload.get(key) or "")
        for key in ("status", "probe_http_status", "apply_status", "apply_http_status", "team_id", "channel_id")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="audit/teams-rsc-dev/evidence.json")
    parser.add_argument("--attempt-apply", action="store_true")
    args = parser.parse_args()

    tenant_id = required("POWER_PLATFORM_TENANT_ID")
    client_id = required("POWER_PLATFORM_CLIENT_ID")
    client_secret = required("POWER_PLATFORM_CLIENT_SECRET")
    team_id = required("PLANNER_TEAMS_DEV_TEAM_ID")
    channel_id = required("PLANNER_TEAMS_DEV_CHANNEL_ID")

    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "capability": "teams-rsc-dev-reconcile",
        "permission": RSC_PERMISSION,
        "team_id": team_id,
        "channel_id": channel_id,
        "run_id": env("GITHUB_RUN_ID"),
        "run_attempt": env("GITHUB_RUN_ATTEMPT"),
        "commit_sha": env("GITHUB_SHA"),
        "started_at": now_iso(),
        "completed_at": None,
        "status": "running",
        "probe_http_status": None,
        "apply_status": None,
        "apply_http_status": None,
        "secret_value_exposed": False,
    }

    try:
        token = graph_token(tenant_id, client_id, client_secret)
        status, http_status = probe_channel(token, team_id, channel_id)
        evidence["status"] = status
        evidence["probe_http_status"] = http_status

        if status == "permission_pending" and args.attempt_apply:
            catalog_app_id = env("TEAMS_RSC_CATALOG_APP_ID")
            bootstrap_client_id = env("TEAMS_RSC_BOOTSTRAP_CLIENT_ID")
            bootstrap_client_secret = env("TEAMS_RSC_BOOTSTRAP_CLIENT_SECRET")
            if not all((catalog_app_id, bootstrap_client_id, bootstrap_client_secret)):
                evidence["apply_status"] = "bootstrap_configuration_missing"
            else:
                bootstrap_token = graph_token(tenant_id, bootstrap_client_id, bootstrap_client_secret)
                apply_status, apply_http = install_with_rsc(bootstrap_token, team_id, catalog_app_id)
                evidence["apply_status"] = apply_status
                evidence["apply_http_status"] = apply_http
                if apply_status in {"applied", "already_installed_or_conflict"}:
                    status, http_status = probe_channel(token, team_id, channel_id)
                    evidence["status"] = status
                    evidence["probe_http_status"] = http_status
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = f"{type(exc).__name__}:{str(exc)[:800]}"

    evidence["completed_at"] = now_iso()
    evidence["state_signature"] = state_signature(evidence)
    path = Path(args.evidence)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": evidence["status"],
        "apply_status": evidence["apply_status"],
        "state_signature": evidence["state_signature"],
        "evidence": str(path),
    }, ensure_ascii=False))
    return 0 if evidence["status"] in {"ready", "permission_pending"} else 1


if __name__ == "__main__":
    sys.exit(main())
