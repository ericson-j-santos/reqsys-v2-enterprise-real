#!/usr/bin/env python3
"""Diagnóstico sanitizado do sync lifecycle Redmine em DEV para a fixture E2E."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request

BASE = os.getenv("REQSYS_E2E_API_BASE_URL", "https://reqsys-api-dev.fly.dev").rstrip("/")
CORRELATION_ID = os.getenv("REQSYS_E2E_CORRELATION_ID", "redmine-lifecycle-probe")
REQ_ID = int(os.getenv("REQSYS_E2E_REQUIREMENT_ID", "8"))
ISSUE_ID = int(os.getenv("REQSYS_E2E_REDMINE_ISSUE_ID", "6"))
REDMINE_BASE = (os.getenv("REDMINE_BASE_URL") or "").strip().rstrip("/")
REDMINE_API_KEY = (os.getenv("REDMINE_API_KEY") or "").strip()


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def redmine_issue() -> dict:
    req = urllib.request.Request(
        f"{REDMINE_BASE}/issues/{ISSUE_ID}.json?include=journals",
        headers={"Accept": "application/json", "X-Redmine-API-Key": REDMINE_API_KEY},
    )
    with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))["issue"]


def expected_fields(req: dict) -> tuple[str, str]:
    urgency = {"alta": "Alta", "media": "Normal", "baixa": "Baixa"}.get(
        str(req.get("urgencia") or "media").lower(), "Normal"
    )
    subject = f"[{req['codigo']}] {req['titulo']}"
    description = (
        f"h2. {req['codigo']} — {req['titulo']}\n\n"
        f"*Sistema:* {req.get('sistema') or ''}\n"
        f"*Área:* {req.get('area') or ''}\n"
        f"*Solicitante:* {req.get('solicitante') or ''}\n"
        f"*Urgência:* {urgency}\n"
        f"*Impacto Regulatório:* {'Sim' if req.get('impacto_regulatorio') else 'Não'}\n\n"
        f"---\n\n"
        f"{req.get('descricao') or ''}"
    )
    return subject, description


_, auth = call("/v1/auth/login", method="POST", payload={})
data = auth.get("data", auth) if isinstance(auth, dict) else {}
token = str(data.get("access_token") or "")
if not token:
    print(json.dumps({"status": "blocked", "reason": "admin_token_missing"}, separators=(",", ":")))
    raise SystemExit(2)

_, requirements_payload = call("/v1/requisitos", token=token)
requirements = requirements_payload.get("data", requirements_payload) if isinstance(requirements_payload, dict) else []
fixture = next((item for item in requirements if int(item.get("id") or 0) == REQ_ID), None)
if not fixture:
    print(json.dumps({"status": "blocked", "reason": "fixture_requirement_missing"}, separators=(",", ":")))
    raise SystemExit(2)

status, result = call(
    f"/v1/requisitos/lifecycle/{REQ_ID}/sincronizar-redmine",
    method="POST",
    payload={"dry_run": False},
    token=token,
)
body = result.get("data", result) if isinstance(result, dict) else result
issue = redmine_issue()
expected_subject, expected_description = expected_fields(fixture)
actual_subject = str(issue.get("subject") or "")
actual_description = str(issue.get("description") or "")

# Não expõe credenciais nem dados reais: a fixture é dedicada ao E2E.
print(json.dumps({
    "status": "pass" if 200 <= status < 300 else "failed",
    "http_status": status,
    "requirement_id": REQ_ID,
    "redmine_issue_id": ISSUE_ID,
    "correlation_id": CORRELATION_ID,
    "detail": result.get("detail") if isinstance(result, dict) else None,
    "mutation_count": body.get("mutation_count") if isinstance(body, dict) else None,
    "subject_equal": expected_subject == actual_subject,
    "description_equal": expected_description == actual_description,
    "expected_description_len": len(expected_description),
    "actual_description_len": len(actual_description),
    "expected_description_sha256": sha(expected_description),
    "actual_description_sha256": sha(actual_description),
    "expected_description_repr": repr(expected_description)[:700],
    "actual_description_repr": repr(actual_description)[:700],
}, ensure_ascii=False, separators=(",", ":")))
raise SystemExit(0 if 200 <= status < 300 else 1)
