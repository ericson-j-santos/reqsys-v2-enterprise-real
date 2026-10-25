#!/usr/bin/env python3
"""Sondagem nativa e somente leitura do Worker Pool no Noteri.

Confere referencia de arquivo (nunca le seu conteudo) e GET /health em loopback.
Nao cria tarefas, altera credenciais, instala servicos ou aciona o Worker Pool.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import socket
from pathlib import Path
from typing import Any, Callable

REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"
REQUEST_ID = "026e9c5add6137dc65e673a6"
CONFIRM = "PROBE-WORKER-POOL-NATIVE"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def health_probe() -> str:
    conn = http.client.HTTPConnection("127.0.0.1", 8097, timeout=3)
    try:
        conn.request("GET", "/health", headers={"Accept": "application/json"})
        resp = conn.getresponse()
        raw = resp.read(4097)
        if len(raw) > 4096:
            return "invalid_response"
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "invalid_response"
        if not isinstance(data, dict) or resp.status not in (200, 503):
            return "invalid_response"
        if resp.status == 200 and data.get("status") == "healthy":
            return (
                "healthy"
                if data.get("auth_configured") is True
                and data.get("expected_rules_sha_configured") is True
                else "not_ready"
            )
        return "not_ready"
    except (OSError, TimeoutError, http.client.HTTPException):
        return "unreachable"
    finally:
        conn.close()


def inspect(
    env: dict[str, str],
    *,
    hostname: str,
    expected_sha: str,
    request_id: str,
    health: Callable[[], str] = health_probe,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema_version": "1",
        "issue_number": 3096,
        "request_id": request_id,
        "base_sha": expected_sha,
        "environment": "local/DEV",
        "expected_host": "noteri",
        "token_reference": "not_checked",
        "pool_health": "not_checked",
        "authenticated_handoff_proven": False,
        "task_enqueued": False,
        "secrets_read": False,
        "production_touched": False,
        "state_changed": False,
        "status": "BLOCKED_EXECUTION_CONTEXT",
    }
    if (
        env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != REPOSITORY
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_SHA", "").lower() != expected_sha
        or not SHA40.fullmatch(expected_sha)
        or hostname.casefold() != "noteri"
        or request_id != REQUEST_ID
    ):
        return evidence
    ref = (
        env.get("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", "").strip()
        or env.get("CODEX_WORKER_POOL_API_TOKEN_FILE", "").strip()
    )
    if not ref:
        evidence["token_reference"] = "missing"
    else:
        path = Path(ref)
        if not path.is_absolute() or path.is_symlink():
            evidence["token_reference"] = "invalid"
        elif path.is_file():
            evidence["token_reference"] = "file_present_unread"
        else:
            evidence["token_reference"] = "file_unavailable"
    observed = health()
    evidence["pool_health"] = observed if observed in {
        "healthy", "not_ready", "unreachable", "invalid_response"
    } else "invalid_response"
    if evidence["token_reference"] != "file_present_unread":
        evidence["status"] = "BLOCKED_TOKEN_REFERENCE"
    elif evidence["pool_health"] != "healthy":
        evidence["status"] = "BLOCKED_NATIVE_POOL_HEALTH"
    else:
        evidence["status"] = "PRECHECK_READY_FOR_AUTHENTICATED_HANDOFF"
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        print(json.dumps({"schema_version": "1", "status": "BLOCKED_CONFIRMATION"}))
        return 2
    report = inspect(
        dict(os.environ),
        hostname=socket.gethostname(),
        expected_sha=args.expected_sha,
        request_id=args.request_id,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PRECHECK_READY_FOR_AUTHENTICATED_HANDOFF" else 2


if __name__ == "__main__":
    raise SystemExit(main())
