#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TIMEOUT_SECONDS = 30.0
DEFAULT_PROCEDURE = "integration.usp_ConsultarPorIdentificadores"


@dataclass(frozen=True)
class ReadinessConfig:
    environment: str
    tenant_id: str
    client_id: str
    client_secret: str
    drive_id: str
    file_id: str
    site_id: str
    list_id: str
    sql_dsn: str
    sql_procedure: str
    power_platform_environment_id: str
    excel_connection_id: str
    sql_connection_id: str
    sharepoint_connection_id: str

    @classmethod
    def from_env(cls) -> "ReadinessConfig":
        return cls(
            environment=os.getenv("INTEGRATION_E2E_ENVIRONMENT", "dev").strip().lower(),
            tenant_id=os.getenv("POWER_PLATFORM_TENANT_ID", "").strip(),
            client_id=os.getenv("POWER_PLATFORM_CLIENT_ID", "").strip(),
            client_secret=os.getenv("POWER_PLATFORM_CLIENT_SECRET", "").strip(),
            drive_id=os.getenv("INTEGRATION_E2E_DRIVE_ID", "").strip(),
            file_id=os.getenv("INTEGRATION_E2E_FILE_ID", "").strip(),
            site_id=os.getenv("INTEGRATION_E2E_SITE_ID", "").strip(),
            list_id=os.getenv("INTEGRATION_E2E_LIST_ID", "").strip(),
            sql_dsn=os.getenv("INTEGRATION_E2E_SQL_DSN", "").strip(),
            sql_procedure=os.getenv("INTEGRATION_E2E_SQL_PROCEDURE", DEFAULT_PROCEDURE).strip(),
            power_platform_environment_id=os.getenv(
                "INTEGRATION_E2E_POWER_PLATFORM_ENVIRONMENT_ID", ""
            ).strip(),
            excel_connection_id=os.getenv("INTEGRATION_E2E_EXCEL_CONNECTION_ID", "").strip(),
            sql_connection_id=os.getenv("INTEGRATION_E2E_SQL_CONNECTION_ID", "").strip(),
            sharepoint_connection_id=os.getenv(
                "INTEGRATION_E2E_SHAREPOINT_CONNECTION_ID", ""
            ).strip(),
        )


class ReadinessError(RuntimeError):
    pass


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_status_{exc.response.status_code}"
    return exc.__class__.__name__


def _required_configuration(config: ReadinessConfig) -> dict[str, bool]:
    return {
        "power_platform_tenant": bool(config.tenant_id),
        "power_platform_client": bool(config.client_id),
        "power_platform_client_secret": bool(config.client_secret),
        "excel_drive": bool(config.drive_id),
        "excel_file": bool(config.file_id),
        "sharepoint_site": bool(config.site_id),
        "sharepoint_list": bool(config.list_id),
        "sql_dsn": bool(config.sql_dsn),
        "sql_procedure": bool(config.sql_procedure),
        "power_platform_environment": bool(config.power_platform_environment_id),
        "excel_connection": bool(config.excel_connection_id),
        "sql_connection": bool(config.sql_connection_id),
        "sharepoint_connection": bool(config.sharepoint_connection_id),
    }


def _graph_token(client: httpx.Client, config: ReadinessConfig) -> str:
    response = client.post(
        f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    token = str(response.json().get("access_token") or "").strip()
    if not token:
        raise ReadinessError("access_token_ausente")
    return token


def _graph_get(client: httpx.Client, path: str, token: str) -> dict[str, Any]:
    response = client.get(
        GRAPH_BASE + path,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _check_sql(config: ReadinessConfig) -> dict[str, Any]:
    try:
        import pyodbc
    except ImportError:
        return {"status": "blocked", "reason": "pyodbc_ausente"}

    connection = None
    try:
        connection = pyodbc.connect(config.sql_dsn, timeout=10)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT CASE WHEN OBJECT_ID(?, 'P') IS NULL THEN 0 ELSE 1 END",
            config.sql_procedure,
        )
        row = cursor.fetchone()
        procedure_exists = bool(row and int(row[0]) == 1)
        return {
            "status": "passed" if procedure_exists else "blocked",
            "procedure_exists": procedure_exists,
            "reason": None if procedure_exists else "stored_procedure_ausente",
        }
    except Exception as exc:  # pragma: no cover - exercitado em DEV real
        return {"status": "blocked", "reason": _safe_error(exc)}
    finally:
        if connection is not None:
            connection.close()


def run_readiness(
    config: ReadinessConfig,
    *,
    client: httpx.Client | None = None,
    sql_checker: Callable[[ReadinessConfig], dict[str, Any]] = _check_sql,
) -> dict[str, Any]:
    if config.environment not in {"dev", "development"}:
        raise ReadinessError("preflight_restrito_a_dev")

    configuration = _required_configuration(config)
    missing = sorted(name for name, configured in configuration.items() if not configured)
    checks: dict[str, Any] = {
        "configuration": {
            "status": "passed" if not missing else "blocked",
            "configured": configuration,
            "missing": missing,
        }
    }

    graph_prerequisites = all(
        configuration[name]
        for name in (
            "power_platform_tenant",
            "power_platform_client",
            "power_platform_client_secret",
            "excel_drive",
            "excel_file",
            "sharepoint_site",
            "sharepoint_list",
        )
    )

    owns_client = client is None
    http_client = client or httpx.Client(follow_redirects=True)
    try:
        if not graph_prerequisites:
            checks["graph_auth"] = {"status": "blocked", "reason": "configuracao_graph_incompleta"}
            checks["excel_source"] = {"status": "blocked", "reason": "configuracao_graph_incompleta"}
            checks["sharepoint_destination"] = {
                "status": "blocked",
                "reason": "configuracao_graph_incompleta",
            }
        else:
            try:
                token = _graph_token(http_client, config)
                checks["graph_auth"] = {"status": "passed"}
            except Exception as exc:
                token = ""
                checks["graph_auth"] = {"status": "blocked", "reason": _safe_error(exc)}

            if token:
                try:
                    excel = _graph_get(
                        http_client,
                        f"/drives/{config.drive_id}/items/{config.file_id}?$select=id,name,eTag",
                        token,
                    )
                    checks["excel_source"] = {
                        "status": "passed" if excel.get("id") else "blocked",
                        "resource_name": str(excel.get("name") or ""),
                        "etag_present": bool(excel.get("eTag")),
                    }
                except Exception as exc:
                    checks["excel_source"] = {"status": "blocked", "reason": _safe_error(exc)}

                try:
                    sharepoint = _graph_get(
                        http_client,
                        f"/sites/{config.site_id}/lists/{config.list_id}?$select=id,name,displayName",
                        token,
                    )
                    checks["sharepoint_destination"] = {
                        "status": "passed" if sharepoint.get("id") else "blocked",
                        "resource_name": str(
                            sharepoint.get("displayName") or sharepoint.get("name") or ""
                        ),
                    }
                except Exception as exc:
                    checks["sharepoint_destination"] = {
                        "status": "blocked",
                        "reason": _safe_error(exc),
                    }
    finally:
        if owns_client:
            http_client.close()

    if configuration["sql_dsn"] and configuration["sql_procedure"]:
        checks["sql_server"] = sql_checker(config)
    else:
        checks["sql_server"] = {"status": "blocked", "reason": "configuracao_sql_incompleta"}

    power_automate_ready = all(
        configuration[name]
        for name in (
            "power_platform_environment",
            "excel_connection",
            "sql_connection",
            "sharepoint_connection",
        )
    )
    checks["power_automate_connections"] = {
        "status": "passed" if power_automate_ready else "blocked",
        "reason": None if power_automate_ready else "connection_references_incompletas",
    }

    blockers = [name for name, result in checks.items() if result.get("status") != "passed"]
    return {
        "ready": not blockers,
        "environment": "dev",
        "checks": checks,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight E2E Excel -> SQL Server -> SharePoint em DEV")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--source-sha", default=os.getenv("GITHUB_SHA", "").strip())
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args()

    correlation_id = args.correlation_id.strip() or str(uuid.uuid4())
    captured_at = datetime.now(timezone.utc).isoformat()
    try:
        result = run_readiness(ReadinessConfig.from_env())
    except Exception as exc:
        result = {
            "ready": False,
            "environment": os.getenv("INTEGRATION_E2E_ENVIRONMENT", "dev").strip().lower(),
            "checks": {},
            "blockers": ["preflight_exception"],
            "error": _safe_error(exc),
        }

    evidence = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_sync",
        "captured_at": captured_at,
        "source_sha": args.source_sha,
        "correlation_id": correlation_id,
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": evidence["ready"], "blockers": evidence["blockers"]}, ensure_ascii=False))
    return 1 if args.strict and not evidence["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
