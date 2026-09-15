#!/usr/bin/env python3
"""E2E determinístico ReqSys ↔ Redmine para a fixture dedicada de DEV.

Pré-condições: requisito sandbox já vinculado a uma única issue Redmine.
O teste prova ida, volta, journal, idempotência e restauração. Segredos ficam
no runtime Fly e nunca são impressos.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

REQSYS_BASE = os.getenv("REQSYS_E2E_API_BASE_URL", "https://reqsys-api-dev.fly.dev").rstrip("/")
CORRELATION_ID = os.getenv("REQSYS_E2E_CORRELATION_ID", "redmine-lifecycle-e2e-v2")
REDMINE_BASE = (os.getenv("REDMINE_BASE_URL") or "").strip().rstrip("/")
REDMINE_API_KEY = (os.getenv("REDMINE_API_KEY") or "").strip()
REDMINE_PROJECT_ID = (os.getenv("REDMINE_PROJECT_ID") or "").strip()
FIXTURE_TITLE = "REQSYS E2E Redmine Lifecycle Sandbox"

EVIDENCE: dict[str, Any] = {
    "schema_version": "2.0.0",
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
        "User-Agent": "reqsys-redmine-lifecycle-e2e/2.0",
        "X-Correlation-Id": CORRELATION_ID,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if redmine:
        headers["X-Redmine-API-Key"] = REDMINE_API_KEY
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=90 if redmine else 45) as response:  # nosec B310
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _data(payload: Any) -> Any:
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def _reqsys(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None) -> Any:
    return _data(_call(f"{REQSYS_BASE}{path}", method=method, payload=payload, bearer=token))


def _redmine(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    return _call(f"{REDMINE_BASE}{path}", method=method, payload=payload, redmine=True)


def _issue(issue_id: int) -> dict[str, Any]:
    return _redmine(f"/issues/{issue_id}.json?include=journals")["issue"]


def _update_issue(issue_id: int, fields: dict[str, Any]) -> None:
    _redmine(f"/issues/{issue_id}.json", method="PUT", payload={"issue": fields})


def _sync(req_id: int, token: str, *, dry_run: bool = False) -> dict[str, Any]:
    return _reqsys(
        f"/v1/requisitos/lifecycle/{req_id}/sincronizar-redmine",
        method="POST",
        payload={"dry_run": dry_run},
        token=token,
    )


def _lifecycle(req_id: int, token: str) -> dict[str, Any]:
    return _reqsys(f"/v1/requisitos/lifecycle/{req_id}", token=token)


def _normalize_eol(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def _expected_owned_fields(req: dict[str, Any]) -> dict[str, str]:
    urgency = {"alta": "Alta", "media": "Normal", "baixa": "Baixa"}.get(
        str(req.get("urgencia") or "media").lower(), "Normal"
    )
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
    return {"subject": f"[{req['codigo']}] {req['titulo']}", "description": description}


def _alternate_status(current_status_id: int) -> int:
    statuses = _redmine("/issue_statuses.json").get("issue_statuses") or []
    candidate = next(
        (s for s in statuses if int(s.get("id") or 0) != current_status_id and not s.get("is_closed")),
        None,
    )
    if candidate is None:
        candidate = next((s for s in statuses if int(s.get("id") or 0) != current_status_id), None)
    if candidate is None:
        raise RuntimeError("não há status Redmine alternativo para o E2E")
    return int(candidate["id"])


def _alternate_assignee(current_assignee_id: int) -> int:
    current_user = (_redmine("/users/current.json").get("user") or {})
    current_user_id = int(current_user.get("id") or 0)
    if current_user_id and current_user_id != current_assignee_id:
        return current_user_id

    memberships = _redmine(
        f"/projects/{int(REDMINE_PROJECT_ID)}/memberships.json?{urllib.parse.urlencode({'limit': 100})}"
    ).get("memberships") or []
    for membership in memberships:
        candidate = int(((membership.get("user") or {}).get("id")) or 0)
        if candidate and candidate != current_assignee_id:
            return candidate
    raise RuntimeError("não há responsável alternativo para o E2E")


def _find_fixture(token: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    requirements = _reqsys("/v1/requisitos", token=token)
    if not isinstance(requirements, list):
        raise RuntimeError("lista de requisitos DEV inválida")
    fixture = next(
        (item for item in requirements if str(item.get("titulo") or "").strip() == FIXTURE_TITLE),
        None,
    )
    if not fixture:
        raise RuntimeError("fixture ReqSys dedicada não encontrada")
    lifecycle = _lifecycle(int(fixture["id"]), token)
    redmine = lifecycle.get("redmine") or {}
    issue_id = int(redmine.get("referencia") or 0)
    if issue_id <= 0:
        raise RuntimeError("fixture ReqSys sem vínculo Redmine")
    return fixture, lifecycle, issue_id


def main() -> int:
    token = ""
    req_id: int | None = None
    issue_id: int | None = None
    original: dict[str, Any] | None = None
    restore_required = False

    try:
        if not REDMINE_BASE or not REDMINE_API_KEY or not REDMINE_PROJECT_ID.isdigit():
            raise RuntimeError("configuração Redmine DEV ausente ou inválida")
        EVIDENCE["checks"]["runtime_redmine_credential_present"] = True

        auth = _reqsys("/v1/auth/login", method="POST", payload={})
        token = str(auth.get("access_token") or "")
        if not token or str((auth.get("usuario") or {}).get("papel") or "") != "admin":
            raise RuntimeError("login DEV não produziu sessão admin")
        EVIDENCE["checks"]["reqsys_admin_session"] = True

        fixture, lifecycle_before, issue_id = _find_fixture(token)
        req_id = int(fixture["id"])
        EVIDENCE["fixture"] = {
            "requisito_id": req_id,
            "codigo": fixture.get("codigo"),
            "redmine_issue_id": issue_id,
            "dedicated": True,
        }
        EVIDENCE["checks"]["fixture_reused"] = True

        # Estabiliza subject/description pelo reconciliador corrigido.
        bootstrap = _sync(req_id, token, dry_run=False)
        EVIDENCE["checks"]["fixture_bootstrap_sync"] = True
        EVIDENCE["bootstrap_mutation_count"] = int(bootstrap.get("mutation_count") or 0)

        # Baseline determinístico: a fixture de teste fica sem responsável.
        _update_issue(issue_id, {"assigned_to_id": ""})
        baseline = _issue(issue_id)
        if (baseline.get("assigned_to") or {}).get("id") is not None:
            raise RuntimeError("Redmine não confirmou desatribuição da fixture com assigned_to_id vazio")
        EVIDENCE["checks"]["unassign_semantics_confirmed"] = True

        expected_owned = _expected_owned_fields(fixture)
        if baseline.get("subject") != expected_owned["subject"]:
            raise RuntimeError("subject canônico ausente após bootstrap")
        if _normalize_eol(baseline.get("description")) != _normalize_eol(expected_owned["description"]):
            raise RuntimeError("description canônica ausente após bootstrap")
        EVIDENCE["checks"]["redmine_direct_read"] = True

        original = {
            "subject": baseline.get("subject") or "",
            "description": baseline.get("description") or "",
            "done_ratio": int(baseline.get("done_ratio") or 0),
            "status_id": int((baseline.get("status") or {}).get("id") or 0),
            "assigned_to_id": None,
        }
        if original["status_id"] <= 0:
            raise RuntimeError("status inicial Redmine inválido")

        dry = _sync(req_id, token, dry_run=True)
        if dry.get("dry_run") is not True or int(dry.get("mutation_count") or 0) != 0:
            raise RuntimeError("dry-run produziu mutação")
        if (dry.get("reqsys_to_redmine") or {}).get("planned"):
            raise RuntimeError("dry-run detectou divergência após bootstrap")
        EVIDENCE["checks"]["dry_run_zero_mutations"] = True

        marker = f"REQSYS-E2E-DIVERGENCE {CORRELATION_ID}"
        restore_required = True
        _update_issue(issue_id, {"subject": marker, "description": marker})
        divergent = _issue(issue_id)
        if divergent.get("subject") != marker or _normalize_eol(divergent.get("description")) != marker:
            raise RuntimeError("pré-condição ReqSys→Redmine não confirmada")
        EVIDENCE["checks"]["forward_precondition_confirmed"] = True

        forward = _sync(req_id, token, dry_run=False)
        after_forward = _issue(issue_id)
        if not (forward.get("reqsys_to_redmine") or {}).get("applied"):
            raise RuntimeError("ReqSys→Redmine não informou aplicação")
        if after_forward.get("subject") != expected_owned["subject"]:
            raise RuntimeError("subject não restaurado pelo sync")
        if _normalize_eol(after_forward.get("description")) != _normalize_eol(expected_owned["description"]):
            raise RuntimeError("description não restaurada pelo sync")
        EVIDENCE["checks"]["reqsys_to_redmine_independent_read"] = True

        ratio0 = int(after_forward.get("done_ratio") or 0)
        ratio1 = 10 if ratio0 != 10 else 20
        status0 = int((after_forward.get("status") or {}).get("id") or 0)
        status1 = _alternate_status(status0)
        assignee1 = _alternate_assignee(0)
        note = f"REQSYS-E2E {CORRELATION_ID}"

        _update_issue(
            issue_id,
            {
                "done_ratio": ratio1,
                "status_id": status1,
                "assigned_to_id": assignee1,
                "notes": note,
            },
        )
        reverse_pre = _issue(issue_id)
        journals = [str(j.get("notes") or "") for j in reverse_pre.get("journals") or []]
        if int(reverse_pre.get("done_ratio") or 0) != ratio1:
            raise RuntimeError("done_ratio de teste não confirmado")
        if int((reverse_pre.get("status") or {}).get("id") or 0) != status1:
            raise RuntimeError("status de teste não confirmado")
        if int((reverse_pre.get("assigned_to") or {}).get("id") or 0) != assignee1:
            raise RuntimeError("responsável de teste não confirmado")
        if note not in journals:
            raise RuntimeError("journal de teste não confirmado")
        EVIDENCE["checks"]["reverse_precondition_confirmed"] = True

        reverse = _sync(req_id, token, dry_run=False)
        execution = (reverse.get("redmine_to_reqsys") or {}).get("execution") or {}
        if int(execution.get("done_ratio") or 0) != ratio1:
            raise RuntimeError("ReqSys não refletiu done_ratio")
        if int(execution.get("status_id") or 0) != status1:
            raise RuntimeError("ReqSys não refletiu status")
        if int(execution.get("assignee_id") or 0) != assignee1:
            raise RuntimeError("ReqSys não refletiu responsável")
        if int((reverse.get("redmine_to_reqsys") or {}).get("imported_comment_count") or 0) < 1:
            raise RuntimeError("ReqSys não importou journal")

        snap_after = _lifecycle(req_id, token)
        sync_links = [
            item for item in (snap_after.get("links") or [])
            if item and item.get("provedor") == "redmine" and item.get("tipo") == "redmine_sync_state"
        ]
        if not sync_links:
            raise RuntimeError("estado de sync não confirmado por leitura independente")
        EVIDENCE["checks"]["redmine_to_reqsys_independent_read"] = True

        repeat = _sync(req_id, token, dry_run=False)
        if int(repeat.get("mutation_count") or 0) != 0:
            raise RuntimeError("repetição idempotente produziu mutação")
        if (repeat.get("redmine_to_reqsys") or {}).get("new_journal_ids"):
            raise RuntimeError("repetição idempotente duplicou journal")
        EVIDENCE["checks"]["idempotent_repeat_zero_mutations"] = True

        EVIDENCE["result"] = {
            "forward_mutation_count": int(forward.get("mutation_count") or 0),
            "reverse_mutation_count": int(reverse.get("mutation_count") or 0),
            "repeat_mutation_count": int(repeat.get("mutation_count") or 0),
            "imported_comment_count": int((reverse.get("redmine_to_reqsys") or {}).get("imported_comment_count") or 0),
            "status_changed": True,
            "assignee_changed": True,
            "done_ratio_changed": True,
            "journal_imported": True,
        }
        EVIDENCE["status"] = "passed"
    except Exception as exc:
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
                        "assigned_to_id": "" if original["assigned_to_id"] is None else original["assigned_to_id"],
                    },
                )
                restored = _issue(issue_id)
                restore_fields = {
                    "subject": restored.get("subject") == original["subject"],
                    "description": _normalize_eol(restored.get("description")) == _normalize_eol(original["description"]),
                    "done_ratio": int(restored.get("done_ratio") or 0) == original["done_ratio"],
                    "status_id": int((restored.get("status") or {}).get("id") or 0) == original["status_id"],
                    "assigned_to_id": (restored.get("assigned_to") or {}).get("id") is None,
                }
                EVIDENCE["restore_field_checks"] = restore_fields
                EVIDENCE["checks"]["restore_confirmed"] = all(restore_fields.values())
                if token and req_id is not None:
                    _sync(req_id, token, dry_run=False)
                if not EVIDENCE["checks"]["restore_confirmed"]:
                    EVIDENCE["status"] = "failed"
                    EVIDENCE["restore_error"] = "restauração não confirmada campo a campo"
            except Exception as restore_exc:
                EVIDENCE["checks"]["restore_confirmed"] = False
                EVIDENCE["status"] = "failed"
                EVIDENCE["restore_error"] = f"{type(restore_exc).__name__}: {restore_exc}"[:500]

    print(json.dumps(EVIDENCE, ensure_ascii=False, separators=(",", ":")))
    return 0 if EVIDENCE["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
