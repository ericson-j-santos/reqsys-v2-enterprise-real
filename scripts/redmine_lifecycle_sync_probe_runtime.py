#!/usr/bin/env python3
"""Diagnóstico sanitizado do sync lifecycle Redmine em DEV para a fixture E2E."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.getenv("REQSYS_E2E_API_BASE_URL", "https://reqsys-api-dev.fly.dev").rstrip("/")
CORRELATION_ID = os.getenv("REQSYS_E2E_CORRELATION_ID", "redmine-lifecycle-probe")
REQ_ID = int(os.getenv("REQSYS_E2E_REQUIREMENT_ID", "8"))


def call(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json", "X-Correlation-Id": CORRELATION_ID}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {}
        detail = parsed.get("detail") if isinstance(parsed, dict) else None
        return exc.code, {"detail": str(detail or body or exc.reason)[:500]}


_, auth = call("/v1/auth/login", method="POST", payload={})
data = auth.get("data", auth) if isinstance(auth, dict) else {}
token = str(data.get("access_token") or "")
if not token:
    print(json.dumps({"status": "blocked", "reason": "admin_token_missing"}, separators=(",", ":")))
    raise SystemExit(2)

status, result = call(
    f"/v1/requisitos/lifecycle/{REQ_ID}/sincronizar-redmine",
    method="POST",
    payload={"dry_run": False},
    token=token,
)
body = result.get("data", result) if isinstance(result, dict) else result
print(json.dumps({
    "status": "pass" if 200 <= status < 300 else "failed",
    "http_status": status,
    "requirement_id": REQ_ID,
    "correlation_id": CORRELATION_ID,
    "detail": result.get("detail") if isinstance(result, dict) else None,
    "mutation_count": body.get("mutation_count") if isinstance(body, dict) else None,
}, ensure_ascii=False, separators=(",", ":")))
raise SystemExit(0 if 200 <= status < 300 else 1)
