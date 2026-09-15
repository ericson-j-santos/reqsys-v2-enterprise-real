#!/usr/bin/env python3
"""E2E governado ReqSys ↔ Redmine executado dentro do runtime DEV.

Cria/reutiliza uma fixture explicitamente dedicada ao E2E quando necessário,
usa apenas credenciais já provisionadas no container, nunca imprime segredos
e restaura os campos mutados ao final. A fixture permanece em DEV para tornar
as próximas execuções idempotentes e não depender de requisitos reais.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

REQSYS_BASE = os.getenv("REQSYS_E2E_API_BASE_URL", "https://reqsys-api-dev.fly.dev").rstrip("/")
CORRELATION_ID = os.getenv("REQSYS_E2E_CORRELATION_ID", "redmine-lifecycle-e2e-runtime")
REDMINE_BASE = (os.getenv("REDMINE_BASE_URL") or "").strip().rstrip("/")
REDMINE_API_KEY = (os.getenv("REDMINE_API_KEY") or "").strip()
REDMINE_PROJECT_ID = (os.getenv("REDMINE_PROJECT_ID") or "").strip()
FIXTURE_TITLE = "REQSYS E2E Redmine Lifecycle Sandbox"
FIXTURE_DESCRIPTION = (
    "Fixture dedicada ao E2E ReqSys ↔ Redmine em DEV. "
    "Critério de aceite: sincronização bidirecional, leitura independente, "
    "journal e repetição idempotente sem duplicidade. Não usar para demanda real."
)

EVIDENCE: dict[str, Any] = {
    "schema_version": "1.1.0",
    "capability": "redmine-lifecycle-e2e",
    "environment": "dev",
    "correlation_id": CORRELATION_ID,
    "mocked": False,
    "simulated": False,
    "status": "running",
    "checks": {},
}


def _call(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    bearer: str | None = None,
    redmine: bool = False,
) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "reqsys-redmine-lifecycle-e2e/1.1",
        "X-Correlation-Id": CORRELATION_ID,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if redmine:
        headers["X-Redmine-API-Key"] = REDMINE_API_KEY
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _reqsys(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
    return _data(_call(f"{REQSYS_BASE}{path}", method=method, payload=payload, bearer=token))


def _redmine(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    return _call(f"{REDMINE_BASE}{path}", method=method, payload=payload, redmine=True)


def _sync(req_id: int, token: str, dry_run: bool = False) -> dict[str, Any]:
    return _reqsys(
        f"/v1/requisitos/lifecycle/{req_id}/sincronizar-redmine",
        method="POST",
        payload={"dry_run": dry_run},
        token=token,
    )


def _lifecycle(req_id: int, token: str) -> dict[str, Any]:
    return _reqsys(f"/v1/requisitos/lifecycle/{req_id}", token=token)


def _issue(issue_id: int) -> dict[str, Any]:
    return _redmine(f"/issues/{issue_id}.json?include=journals")["issue"]


def _update_issue(issue_id: int, fields: dict[str, Any]) -> None:
    _redmine(f"/issues/{issue_id}.json", method="PUT", payload={"issue": fields})


def _create_requirement() -> dict[str, Any]:
    return _reqsys(
        "/v1/requisitos",
        method="POST",
        payload={
            "titulo": FIXTURE_TITLE,
            "descricao": FIXTURE_DESCRIPTION,
            "urgencia": "baixa",
            "area": "E2E",
            "sistema": "ReqSys",
            "solicitante": "automation",
            "impacto_regulatorio": False,
        },
    )


def _create_redmine_fixture_issue(req: dict[str, Any]) -> int:
    created = _redmine(
        "/issues.json",
        method="POST",
        payload={
            "issue": {
                "project_id": int(REDMINE_PROJECT_ID),
                "subject": req["titulo"],
                "description": req.get("descricao") or "",
            }
        },
    )
    issue_id = int((created.get("issue") or {}).get("id") or 0)
    if issue_id <= 0:
        raise RuntimeError("Redmine não retornou id ao criar fixture")
    return issue_id


def _link_fixture(req: dict[str, Any], issue_id: int) -> None:
    _reqsys(
        f"/v1/rastreabilidade/requisitos/{int(req['id'])}/vinculos",
        method="POST",
        payload={
            "tipo": "issue",
            "provedor": "redmine",
            "repo": "redmine",
            "referencia": str(issue_id),
            "url": f"{REDMINE_BASE}/issues/{issue_id}",
            "titulo": f"{FIXTURE_TITLE} — Redmine #{issue_id}",
            "autor": "reqsys-e2e",
            "ambiente": "dev",
        },
    )


def _ensure_fixture(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    requirements = _reqsys("/v1/requisitos")
    if not isinstance(requirements, list):
        raise RuntimeError("lista de requisitos DEV inválida")
    EVIDENCE["checks"]["requirements_read"] = len(requirements)

    exact = next((req for req in requirements if str(req.get("titulo") or "").strip() == FIXTURE_TITLE), None)
    created_requirement = False
    if exact is None:
        exact = _create_requirement()
        created_requirement = True
        EVIDENCE["checks"]["fixture_requirement_created"] = True
    else:
        EVIDENCE["checks"]["fixture_requirement_reused"] = True

    req_id = int(exact["id"])
    snap = _lifecycle(req_id, token)
    redmine = snap.get("redmine") or {}
    if redmine.get("referencia") and redmine.get("url"):
        EVIDENCE["checks"]["fixture_redmine_link_reused"] = True
        return exact, snap

    issue_id: int | None = None
    try:
        issue_id = _create_redmine_fixture_issue(exact)
        _link_fixture(exact, issue_id)
        EVIDENCE["checks"]["fixture_redmine_issue_created"] = True
        snap = _lifecycle(req_id, token)
        redmine = snap.get("redmine") or {}
        if int(redmine.get("referencia") or 0) != issue_id:
            raise RuntimeError("vínculo Redmine da fixture não foi confirmado pelo lifecycle")
        EVIDENCE["checks"]["fixture_link_independent_read"] = True
        return exact, snap
    except Exception:
        if issue_id is not None:
            try:
                _redmine(f"/issues/{issue_id}.json", method="DELETE")
                EVIDENCE["checks"]["partial_fixture_redmine_rollback"] = True
            except Exception:
                EVIDENCE["checks"]["partial_fixture_redmine_rollback"] = False
        if created_requirement:
            EVIDENCE["checks"]["partial_fixture_requirement_retained_for_retry"] = True
        raise


def _alternate_assignee(project_id: int, current_assignee_id: int) -> int:
    current = (_redmine("/users/current.json").get("user") or {})
    current_user_id = int(current.get("id") or 0)
    if current_user_id and current_user_id != current_assignee_id:
        return current_user_id

    memberships = _redmine(f"/projects/{project_id}/memberships.json?limit=100").get("memberships") or []
    for membership in memberships:
        candidate = int(((membership.get("user") or {}).get("id")) or 0)
        if candidate and candidate != current_assignee_id:
            return candidate
    raise RuntimeError("não há responsável alternativo no projeto Redmine para provar mudança de responsável")


def main() -> int:
    token = ""
    issue_id: int | None = None
    req_id: int | None = None
    original: dict[str, Any] | None = None
    restore_required = False

    try:
        if not REDMINE_BASE or not REDMINE_API_KEY or not REDMINE_PROJECT_ID.isdigit():
            raise RuntimeError("REDMINE_BASE_URL/REDMINE_API_KEY/REDMINE_PROJECT_ID ausente ou inválido no runtime DEV")
        EVIDENCE["checks"]["runtime_redmine_credential_present"] = True

        auth = _reqsys("/v1/auth/login", method="POST", payload={})
        token = str(auth.get("access_token") or "")
        papel = str((auth.get("usuario") or {}).get("papel") or "")
        if not token or papel != "admin":
            raise RuntimeError("login demo DEV não produziu sessão admin")
        EVIDENCE["checks"]["reqsys_admin_session"] = True

        fixture, lifecycle_before = _ensure_fixture(token)
        req_id = int(fixture["id"])
        issue_id = int((lifecycle_before.get("redmine") or {})["referencia"])
        EVIDENCE["fixture"] = {
            "requisito_id": req_id,
            "codigo": fixture.get("codigo"),
            "redmine_issue_id": issue_id,
            "dedicated": True,
        }

        before = _issue(issue_id)
        original = {
            "subject": before.get("subject") or "",
            "description": before.get("description") or "",
            "done_ratio": before.get("done_ratio"),
            "status_id": int((before.get("status") or {}).get("id") or 0),
            "assigned_to_id": (before.get("assigned_to") or {}).get("id"),
        }
        if original["status_id"] <= 0:
            raise RuntimeError("status inicial da fixture Redmine inválido")
        EVIDENCE["checks"]["redmine_direct_read"] = True

        dry = _sync(req_id, token, dry_run=True)
        if dry.get("dry_run") is not True or int(dry.get("mutation_count") or 0) != 0:
            raise RuntimeError("dry_run não provou ausência de mutação")
        EVIDENCE["checks"]["dry_run_zero_mutations"] = True

        marker = f"REQSYS-E2E-DIVERGENCE {CORRELATION_ID}"
        restore_required = True
        _update_issue(issue_id, {"subject": marker, "description": marker})
        divergent = _issue(issue_id)
        if divergent.get("subject") != marker or divergent.get("description") != marker:
            raise RuntimeError("pré-condição ReqSys→Redmine não confirmada por leitura direta")
        EVIDENCE["checks"]["forward_precondition_confirmed"] = True

        forward = _sync(req_id, token, dry_run=False)
        after_forward = _issue(issue_id)
        if not (forward.get("reqsys_to_redmine") or {}).get("applied"):
            raise RuntimeError("sincronização ReqSys→Redmine não informou aplicação")
        if after_forward.get("subject") != fixture.get("titulo") or after_forward.get("description") != (fixture.get("descricao") or ""):
            raise RuntimeError("leitura direta Redmine não confirmou conteúdo canônico do ReqSys")
        EVIDENCE["checks"]["reqsys_to_redmine_independent_read"] = True

        ratio0 = int(after_forward.get("done_ratio") or 0)
        ratio1 = 10 if ratio0 != 10 else 20
        status0 = int((after_forward.get("status") or {}).get("id") or 0)
        statuses = _redmine("/issue_statuses.json").get("issue_statuses") or []
        alternate_status = next((s for s in statuses if int(s.get("id") or 0) != status0 and not s.get("is_closed")), None)
        if alternate_status is None:
            alternate_status = next((s for s in statuses if int(s.get("id") or 0) != status0), None)
        if alternate_status is None:
            raise RuntimeError("não há status Redmine alternativo para provar sincronização de status")
        expected_status_id = int(alternate_status["id"])

        assigned0 = int((after_forward.get("assigned_to") or {}).get("id") or 0)
        expected_assignee_id = _alternate_assignee(int(REDMINE_PROJECT_ID), assigned0)
        if expected_assignee_id == assigned0:
            raise RuntimeError("responsável alternativo não divergiu do valor inicial")

        note = f"REQSYS-E2E {CORRELATION_ID}"
        reverse_fields: dict[str, Any] = {
            "done_ratio": ratio1,
            "status_id": expected_status_id,
            "assigned_to_id": expected_assignee_id,
            "notes": note,
        }
        _update_issue(issue_id, reverse_fields)
        reverse_pre = _issue(issue_id)
        journal_texts = [str(j.get("notes") or "") for j in reverse_pre.get("journals") or []]
        if int(reverse_pre.get("done_ratio") or 0) != ratio1:
            raise RuntimeError("pré-condição done_ratio Redmine→ReqSys não confirmada")
        if int((reverse_pre.get("status") or {}).get("id") or 0) != expected_status_id:
            raise RuntimeError("mudança de status Redmine não foi confirmada")
        if int((reverse_pre.get("assigned_to") or {}).get("id") or 0) != expected_assignee_id:
            raise RuntimeError("mudança de responsável Redmine não foi confirmada")
        if note not in journal_texts:
            raise RuntimeError("journal E2E não foi confirmado por leitura direta")
        EVIDENCE["checks"]["reverse_precondition_confirmed"] = True

        reverse = _sync(req_id, token, dry_run=False)
        execution = (reverse.get("redmine_to_reqsys") or {}).get("execution") or {}
        if int(execution.get("done_ratio") or 0) != ratio1:
            raise RuntimeError("snapshot ReqSys não refletiu done_ratio do Redmine")
        if int(execution.get("status_id") or 0) != expected_status_id:
            raise RuntimeError("snapshot ReqSys não refletiu status do Redmine")
        if int(execution.get("assignee_id") or 0) != expected_assignee_id:
            raise RuntimeError("snapshot ReqSys não refletiu responsável do Redmine")
        if int((reverse.get("redmine_to_reqsys") or {}).get("imported_comment_count") or 0) < 1:
            raise RuntimeError("journal E2E não foi importado pelo ReqSys")

        snap_after = _lifecycle(req_id, token)
        sync_links = [
            item for item in (snap_after.get("links") or [])
            if item and item.get("provedor") == "redmine" and item.get("tipo") == "redmine_sync_state"
        ]
        if not sync_links:
            raise RuntimeError("estado de sincronização não confirmado por leitura independente no ReqSys")
        EVIDENCE["checks"]["redmine_to_reqsys_independent_read"] = True

        repeat = _sync(req_id, token, dry_run=False)
        if int(repeat.get("mutation_count") or 0) != 0:
            raise RuntimeError("repetição idempotente produziu mutação")
        if (repeat.get("redmine_to_reqsys") or {}).get("new_journal_ids"):
            raise RuntimeError("repetição idempotente duplicou journal")
        EVIDENCE["checks"]["idempotent_repeat_zero_mutations"] = True

        EVIDENCE["result"] = {
            "forward_mutation_count": forward.get("mutation_count"),
            "reverse_mutation_count": reverse.get("mutation_count"),
            "repeat_mutation_count": repeat.get("mutation_count"),
            "imported_comment_count": (reverse.get("redmine_to_reqsys") or {}).get("imported_comment_count"),
            "status_changed": True,
            "assignee_changed": True,
            "done_ratio_changed": True,
            "journal_imported": True,
        }
        EVIDENCE["status"] = "passed"
    except Exception as exc:
        if EVIDENCE.get("status") == "running":
            EVIDENCE["status"] = "failed" if restore_required else "blocked"
        EVIDENCE["error"] = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        if restore_required and issue_id is not None and original is not None:
            try:
                _update_issue(
                    issue_id,
                    {
                        "subject": original["subject"],
                        "description": original["description"],
                        "done_ratio": original["done_ratio"],
                        "status_id": original["status_id"],
                        "assigned_to_id": original["assigned_to_id"],
                    },
                )
                restored = _issue(issue_id)
                EVIDENCE["checks"]["restore_confirmed"] = (
                    restored.get("subject") == original["subject"]
                    and restored.get("description") == original["description"]
                    and restored.get("done_ratio") == original["done_ratio"]
                    and int((restored.get("status") or {}).get("id") or 0) == original["status_id"]
                    and ((restored.get("assigned_to") or {}).get("id") or None) == (original["assigned_to_id"] or None)
                )
                if token and req_id is not None:
                    _sync(req_id, token, dry_run=False)
                if not EVIDENCE["checks"]["restore_confirmed"]:
                    EVIDENCE["status"] = "failed"
                    EVIDENCE["restore_error"] = "restauração não confirmada por leitura direta"
            except Exception as restore_exc:
                EVIDENCE["checks"]["restore_confirmed"] = False
                EVIDENCE["status"] = "failed"
                EVIDENCE["restore_error"] = f"{type(restore_exc).__name__}: {restore_exc}"[:500]

    print(json.dumps(EVIDENCE, ensure_ascii=False, separators=(",", ":")))
    return 0 if EVIDENCE["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
