#!/usr/bin/env python3
"""Reconcilia o owner Flow Bot do PC24x7 DEV sem expor credenciais."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONFIRMATION = "RECONCILE-PC24X7-TEAMS-FLOW-BOT-DEV"
ALLOWED_DEV_ENVIRONMENTS = {
    "dev",
    "development",
    "desenvolvimento",
    "local",
    "test",
    "teste",
}


class ReconcileError(RuntimeError):
    pass


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_api_base(value: str) -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not host.endswith(".trycloudflare.com")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ReconcileError("api_base_not_governed_pc24x7_https")
    return f"https://{host}"


def _request_json(
    method: str,
    url: str,
    *,
    correlation_id: str,
    admin_jwt: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "reqsys-pc24x7-teams-flow-bot-reconcile/1.0",
        "X-Correlation-ID": correlation_id,
    }
    if admin_jwt:
        headers["Authorization"] = f"Bearer {admin_jwt}"
    body = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            raw = response.read(262_144).decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ReconcileError(f"api_http_{exc.code}:{urlparse(url).path}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = f"api_unavailable:{urlparse(url).path}:{type(exc).__name__}"
        raise ReconcileError(detail) from None
    if not 200 <= status < 300:
        raise ReconcileError(f"api_http_{status}:{urlparse(url).path}")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReconcileError(f"api_invalid_json:{urlparse(url).path}") from exc
    if not isinstance(decoded, dict) or decoded.get("success") is False:
        raise ReconcileError(f"api_invalid_envelope:{urlparse(url).path}")
    return decoded


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data", payload)
    if not isinstance(value, dict):
        raise ReconcileError("api_data_not_object")
    return value


def _resolve_admin_jwt(
    base: str,
    configured_jwt: str,
    owner_email: str,
    correlation_id: str,
) -> tuple[str, str, bool]:
    try:
        session = _request_json(
            "GET",
            f"{base}/api/v1/auth/session",
            correlation_id=f"{correlation_id}-admin-check",
            admin_jwt=configured_jwt,
        )
        if str(_data(session).get("papel") or "").casefold() == "admin":
            return configured_jwt, "environment_secret_valid", False
    except ReconcileError as exc:
        if not str(exc).startswith(("api_http_401:", "api_http_403:")):
            raise

    config = _data(
        _request_json(
            "GET",
            f"{base}/api/v1/auth/config",
            correlation_id=f"{correlation_id}-auth-config",
        )
    )
    environment = str(config.get("environment") or "").strip().casefold()
    if environment not in ALLOWED_DEV_ENVIRONMENTS:
        raise ReconcileError("admin_auth_refused_non_dev_environment")
    if config.get("demo_login_enabled") is not True:
        raise ReconcileError("admin_auth_unavailable_demo_login_disabled")

    login = _data(
        _request_json(
            "POST",
            f"{base}/api/v1/auth/login",
            correlation_id=f"{correlation_id}-dev-login",
            payload={"email": owner_email},
        )
    )
    user = login.get("usuario") if isinstance(login.get("usuario"), dict) else {}
    fresh_jwt = str(login.get("access_token") or "").strip()
    if str(user.get("papel") or "").casefold() != "admin" or not fresh_jwt:
        raise ReconcileError("admin_auth_dev_login_not_admin")

    fresh_session = _request_json(
        "GET",
        f"{base}/api/v1/auth/session",
        correlation_id=f"{correlation_id}-fresh-admin-check",
        admin_jwt=fresh_jwt,
    )
    if str(_data(fresh_session).get("papel") or "").casefold() != "admin":
        raise ReconcileError("admin_auth_fresh_session_not_admin")
    return fresh_jwt, "dev_demo_ephemeral", True


def reconcile(
    *,
    api_base: str,
    admin_jwt: str,
    webhook_url: str,
    owner_email: str,
    recipient: str,
    correlation_id: str,
) -> dict[str, Any]:
    base = _validate_api_base(api_base)
    if not admin_jwt.strip():
        raise ReconcileError("admin_jwt_missing")
    webhook = webhook_url.strip()
    webhook_parsed = urlparse(webhook)
    if webhook_parsed.scheme != "https" or not webhook_parsed.hostname:
        raise ReconcileError("flow_bot_webhook_not_https")
    owner = owner_email.strip()
    target = recipient.strip()
    if "@" not in owner:
        raise ReconcileError("owner_email_invalid")
    if "@" not in target:
        raise ReconcileError("recipient_invalid")

    effective_admin_jwt, admin_auth_source, admin_jwt_refreshed = _resolve_admin_jwt(
        base,
        admin_jwt,
        owner,
        correlation_id,
    )

    owners_payload = _request_json(
        "GET",
        f"{base}/v1/teams-gateway/flow-bot/owners",
        correlation_id=correlation_id,
        admin_jwt=effective_admin_jwt,
    )
    items = _data(owners_payload).get("items", [])
    if not isinstance(items, list):
        raise ReconcileError("owners_not_list")
    matching = next(
        (
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get("owner_email") or "").casefold() == owner.casefold()
        ),
        None,
    )
    owner_payload = {
        "webhook_url": webhook,
        "prioridade": 10,
        "ativo": True,
        "observacao": "webhook reconciliado pelo workflow governado PC24x7 DEV",
    }
    if matching is None:
        owner_payload["owner_email"] = owner
        changed = _request_json(
            "POST",
            f"{base}/v1/teams-gateway/flow-bot/owners",
            correlation_id=correlation_id,
            admin_jwt=effective_admin_jwt,
            payload=owner_payload,
        )
        action = "created"
    else:
        owner_id = matching.get("id")
        if not isinstance(owner_id, int) or owner_id <= 0:
            raise ReconcileError("owner_id_invalid")
        changed = _request_json(
            "PATCH",
            f"{base}/v1/teams-gateway/flow-bot/owners/{owner_id}",
            correlation_id=correlation_id,
            admin_jwt=effective_admin_jwt,
            payload=owner_payload,
        )
        action = "updated"
    changed_data = _data(changed)
    owner_id = changed_data.get("id")

    status_payload = _request_json(
        "GET",
        f"{base}/v1/teams-gateway/status",
        correlation_id=correlation_id,
    )
    routes = _data(status_payload).get("rotas", [])
    route = next(
        (
            item
            for item in routes
            if isinstance(item, dict) and item.get("canal") == "flow_bot"
        ),
        {},
    )
    if route.get("disponivel") is not True or int(route.get("donos_ativos") or 0) < 1:
        raise ReconcileError("flow_bot_route_not_ready_after_reconcile")

    send_payload = {
        "destino_tipo": "chat",
        "modo": "flow_bot",
        "destino_id": target,
        "texto": "ReqSys PC24x7 DEV: Flow Bot reconciliado e validado.",
        "content_type": "text",
        "autor": "reqsys-pc24x7-reconcile",
        "permitir_fallback": False,
        "dry_run": False,
        "metadata": {"event_type": "pc24x7-flow-bot-reconcile"},
    }
    delivery = _data(
        _request_json(
            "POST",
            f"{base}/v1/teams-gateway/messages",
            correlation_id=correlation_id,
            payload=send_payload,
        )
    )
    if delivery.get("entregue") is not True:
        raise ReconcileError("flow_bot_delivery_not_confirmed")

    return {
        "schema_version": "1.0.0",
        "status": "ready",
        "environment": "dev",
        "action": action,
        "admin_auth_source": admin_auth_source,
        "admin_jwt_refreshed": admin_jwt_refreshed,
        "owner_id": owner_id,
        "owner_email_sha256": _fingerprint(owner.casefold()),
        "recipient_sha256": _fingerprint(target.casefold()),
        "webhook_sha256": _fingerprint(webhook),
        "flow_bot_available": True,
        "active_owners": int(route.get("donos_ativos") or 0),
        "delivery_confirmed": True,
        "delivery_status_code": delivery.get("status_code"),
        "delivery_correlation_id": delivery.get("correlation_id"),
        "correlation_id": correlation_id,
        "secret_value_exposed": False,
        "production_touched": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--api-base", default=os.getenv("REQSYS_API_BASE_URL", ""))
    parser.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID", ""))
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/pc24x7-teams-flow-bot-reconcile/evidence.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    correlation_id = args.correlation_id.strip() or f"pc24x7-flow-bot-{uuid.uuid4()}"
    try:
        if args.confirm != CONFIRMATION:
            raise ReconcileError(f"confirmation_required:{CONFIRMATION}")
        evidence = reconcile(
            api_base=args.api_base,
            admin_jwt=os.getenv("COFRE_ADMIN_JWT", ""),
            webhook_url=os.getenv("TEAMS_FLOW_BOT_WEBHOOK_URL", ""),
            owner_email=os.getenv("TEAMS_FLOW_BOT_OWNER_EMAIL", ""),
            recipient=os.getenv("TEAMS_FLOW_BOT_RECIPIENT", ""),
            correlation_id=correlation_id,
        )
        exit_code = 0
    except Exception as exc:
        detail = (
            str(exc)[:240]
            if isinstance(exc, ReconcileError)
            else "unexpected_error"
        )
        evidence = {
            "schema_version": "1.0.0",
            "status": "blocked",
            "environment": "dev",
            "correlation_id": correlation_id,
            "reason": type(exc).__name__,
            "detail": detail,
            "secret_value_exposed": False,
            "production_touched": False,
        }
        exit_code = 4
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
