#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GROUP_NAME = "ReqSys WSJF DEV"
PLAN_NAME = "WSJF DEV"
BUCKET_NAME = "Backlog"
FILE_NAME = "WSJF.xlsx"
TABLE_NAME = "tbDemandas"
TIMEOUT = 30.0


class BootstrapError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BootstrapError(f"Variável obrigatória ausente: {name}")
    return value


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16] if value else ""


def _validate_template(path: Path) -> None:
    if not path.exists():
        raise BootstrapError(f"Template não encontrado: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            tables = []
            for name in archive.namelist():
                if not name.startswith("xl/tables/") or not name.endswith(".xml"):
                    continue
                text = archive.read(name).decode("utf-8", errors="replace")
                match = re.search(r'\bname="([^"]+)"', text)
                if match:
                    tables.append(match.group(1))
    except zipfile.BadZipFile as exc:
        raise BootstrapError("WSJF.xlsx não é um XLSX válido") from exc
    if TABLE_NAME not in tables:
        raise BootstrapError(f"Template WSJF.xlsx não contém a tabela {TABLE_NAME}")


def _token(client: httpx.Client) -> str:
    tenant = _required("POWER_PLATFORM_TENANT_ID")
    client_id = _required("POWER_PLATFORM_CLIENT_ID")
    secret = _required("POWER_PLATFORM_CLIENT_SECRET")
    response = client.post(
        TOKEN_URL.format(tenant=tenant),
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        raise BootstrapError(f"Falha ao obter token Microsoft Graph: HTTP {response.status_code}")
    token = str(response.json().get("access_token") or "")
    if not token:
        raise BootstrapError("Microsoft Graph não retornou access_token")
    return token


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
        return str((payload.get("error") or {}).get("code") or "")[:120]
    except Exception:
        return ""


def _graph(
    client: httpx.Client,
    method: str,
    path: str,
    token: str,
    *,
    allow_status: tuple[int, ...] = (),
    **kwargs: Any,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(kwargs.pop("headers", {}))
    url = GRAPH + path
    last: httpx.Response | None = None
    for attempt in range(6):
        response = client.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
        last = response
        if response.status_code in allow_status:
            return response
        if response.status_code < 400:
            return response
        if response.status_code in (429, 502, 503, 504) and attempt < 5:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 20)
            time.sleep(wait)
            continue
        code = _error_code(response)
        suffix = f" ({code})" if code else ""
        raise BootstrapError(f"Microsoft Graph {method} {path.split('?')[0]}: HTTP {response.status_code}{suffix}")
    assert last is not None
    raise BootstrapError(f"Microsoft Graph indisponível após retentativas: {method} {path.split('?')[0]}")


def _find_or_create_group(client: httpx.Client, token: str) -> tuple[dict[str, Any], bool]:
    response = _graph(
        client,
        "GET",
        "/groups",
        token,
        params={
            "$filter": f"displayName eq '{GROUP_NAME.replace("'", "''")}'",
            "$select": "id,displayName,groupTypes,mailNickname",
            "$top": "10",
        },
    )
    exact = [g for g in response.json().get("value", []) if str(g.get("displayName") or "") == GROUP_NAME]
    if len(exact) > 1:
        raise BootstrapError(f"Existem {len(exact)} grupos com o nome {GROUP_NAME}; criação interrompida para evitar ambiguidade")
    if exact:
        group = exact[0]
        if "Unified" not in (group.get("groupTypes") or []):
            raise BootstrapError(f"{GROUP_NAME} existe, mas não é um Grupo Microsoft 365")
        return group, False

    client_id = _required("POWER_PLATFORM_CLIENT_ID")
    nicknames = ["reqsys-wsjf-dev", f"reqsys-wsjf-dev-{_hash(client_id)[:6]}"]
    last_error: BootstrapError | None = None
    for nickname in nicknames:
        try:
            created = _graph(
                client,
                "POST",
                "/groups",
                token,
                headers={"Content-Type": "application/json"},
                json={
                    "displayName": GROUP_NAME,
                    "description": "Recursos isolados de desenvolvimento para o MVP WSJF Planner → Excel do ReqSys.",
                    "groupTypes": ["Unified"],
                    "mailEnabled": True,
                    "mailNickname": nickname,
                    "securityEnabled": False,
                    "visibility": "Private",
                },
            ).json()
            return created, True
        except BootstrapError as exc:
            last_error = exc
            if "HTTP 400" not in str(exc):
                raise
    assert last_error is not None
    raise last_error


def _wait_drive(client: httpx.Client, token: str, group_id: str) -> dict[str, Any]:
    deadline = time.time() + 600
    last_status = None
    while time.time() < deadline:
        response = _graph(
            client,
            "GET",
            f"/groups/{group_id}/drive?$select=id,driveType,webUrl",
            token,
            allow_status=(400, 404),
        )
        if response.status_code < 400:
            return response.json()
        last_status = response.status_code
        time.sleep(15)
    raise BootstrapError(f"SharePoint/drive do grupo não ficou disponível em 10 minutos (último HTTP {last_status})")


def _find_or_create_plan(client: httpx.Client, token: str, group_id: str) -> tuple[dict[str, Any], bool]:
    plans = _graph(client, "GET", f"/groups/{group_id}/planner/plans", token).json().get("value", [])
    exact = [p for p in plans if str(p.get("title") or "") == PLAN_NAME]
    if len(exact) > 1:
        raise BootstrapError(f"Existem {len(exact)} Planners chamados {PLAN_NAME}; criação interrompida")
    if exact:
        return exact[0], False
    created = _graph(
        client,
        "POST",
        "/planner/plans",
        token,
        headers={"Content-Type": "application/json"},
        json={
            "container": {"url": f"{GRAPH}/groups/{group_id}"},
            "title": PLAN_NAME,
        },
    ).json()
    return created, True


def _find_or_create_bucket(client: httpx.Client, token: str, plan_id: str) -> tuple[dict[str, Any], bool]:
    buckets = _graph(client, "GET", f"/planner/plans/{plan_id}/buckets", token).json().get("value", [])
    exact = [b for b in buckets if str(b.get("name") or "") == BUCKET_NAME]
    if len(exact) > 1:
        raise BootstrapError(f"Existem {len(exact)} buckets chamados {BUCKET_NAME}; criação interrompida")
    if exact:
        return exact[0], False
    created = _graph(
        client,
        "POST",
        "/planner/buckets",
        token,
        headers={"Content-Type": "application/json"},
        json={"name": BUCKET_NAME, "planId": plan_id, "orderHint": " !"},
    ).json()
    return created, True


def _xlsx_has_table(data: bytes) -> bool:
    try:
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for name in archive.namelist():
                if not name.startswith("xl/tables/") or not name.endswith(".xml"):
                    continue
                text = archive.read(name).decode("utf-8", errors="replace")
                if re.search(rf'\bname="{re.escape(TABLE_NAME)}"', text):
                    return True
    except zipfile.BadZipFile:
        return False
    return False


def _find_or_create_file(
    client: httpx.Client, token: str, drive_id: str, template: Path
) -> tuple[dict[str, Any], bool]:
    existing = _graph(
        client,
        "GET",
        f"/drives/{drive_id}/root:/{FILE_NAME}",
        token,
        allow_status=(404,),
    )
    if existing.status_code != 404:
        item = existing.json()
        content = _graph(client, "GET", f"/drives/{drive_id}/items/{item['id']}/content", token).content
        if not _xlsx_has_table(content):
            raise BootstrapError(f"{FILE_NAME} já existe, mas não contém {TABLE_NAME}; arquivo existente foi preservado")
        return item, False

    data = template.read_bytes()
    uploaded = _graph(
        client,
        "PUT",
        f"/drives/{drive_id}/root:/{FILE_NAME}:/content",
        token,
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        content=data,
    ).json()
    verify = _graph(client, "GET", f"/drives/{drive_id}/items/{uploaded['id']}/content", token).content
    if not _xlsx_has_table(verify):
        raise BootstrapError(f"Upload concluído, mas {TABLE_NAME} não foi encontrada na validação pós-upload")
    return uploaded, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria/reutiliza recursos Microsoft 365 para o WSJF DEV")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    evidence: dict[str, Any] = {
        "environment": "dev",
        "group": {"name": GROUP_NAME, "status": "pending"},
        "planner": {"name": PLAN_NAME, "status": "pending"},
        "bucket": {"name": BUCKET_NAME, "status": "pending"},
        "workbook": {"name": FILE_NAME, "table": TABLE_NAME, "status": "pending"},
        "status": "BLOCKED",
    }

    try:
        _validate_template(args.template)
        with httpx.Client(follow_redirects=True) as client:
            token = _token(client)
            group, group_created = _find_or_create_group(client, token)
            group_id = str(group.get("id") or "")
            if not group_id:
                raise BootstrapError("Grupo Microsoft 365 sem id")
            evidence["group"] = {"name": GROUP_NAME, "status": "created" if group_created else "reused", "id_hash": _hash(group_id)}

            drive = _wait_drive(client, token, group_id)
            drive_id = str(drive.get("id") or "")
            if not drive_id:
                raise BootstrapError("Drive SharePoint sem id")

            plan, plan_created = _find_or_create_plan(client, token, group_id)
            plan_id = str(plan.get("id") or "")
            if not plan_id:
                raise BootstrapError("Planner sem id")
            evidence["planner"] = {"name": PLAN_NAME, "status": "created" if plan_created else "reused", "id_hash": _hash(plan_id)}

            bucket, bucket_created = _find_or_create_bucket(client, token, plan_id)
            bucket_id = str(bucket.get("id") or "")
            evidence["bucket"] = {"name": BUCKET_NAME, "status": "created" if bucket_created else "reused", "id_hash": _hash(bucket_id)}

            workbook, workbook_created = _find_or_create_file(client, token, drive_id, args.template)
            file_id = str(workbook.get("id") or "")
            evidence["workbook"] = {
                "name": FILE_NAME,
                "table": TABLE_NAME,
                "status": "created" if workbook_created else "reused",
                "id_hash": _hash(file_id),
                "drive_id_hash": _hash(drive_id),
                "template_sha256": hashlib.sha256(args.template.read_bytes()).hexdigest(),
            }
            evidence["status"] = "PASS"
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
