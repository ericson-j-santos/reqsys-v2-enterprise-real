#!/usr/bin/env python3
"""Cliente governado para manutenção do control plane do Desktop PC24x7.

Escopo intencionalmente fechado:
- destino fixo DESKTOP-PDQK954:18787;
- somente status e ações versionadas de recuperação;
- sem shell/comando arbitrário, reboot, segredo ou produção;
- submissão idempotente + leitura terminal independente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

EXPECTED_HOST = "DESKTOP-PDQK954"
DEFAULT_ENDPOINT = f"http://{EXPECTED_HOST}:18787"
EXPECTED_PORT = 18787
TERMINAL_STATUSES = {"CONCLUÍDO", "BLOQUEADO", "CANCELADO"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

ACTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "rdc": {
        "task_type": "host.rdc.recover.v1",
        "risk": 2,
        "payload": {"target_host": EXPECTED_HOST, "force_restart": True},
    },
    "github-runner": {
        "task_type": "host.github_runner.recover.v1",
        "risk": 2,
        "payload": {"target_host": EXPECTED_HOST},
    },
    "refresh": {
        "task_type": "host.orchestrator.refresh.v1",
        "risk": 2,
        "payload": {"target_host": EXPECTED_HOST},
    },
}


class MaintenanceClientError(RuntimeError):
    pass


def validate_endpoint(raw: str) -> str:
    parsed = urllib.parse.urlparse(str(raw).strip())
    if parsed.scheme != "http":
        raise MaintenanceClientError("endpoint deve usar http")
    if parsed.username or parsed.password:
        raise MaintenanceClientError("endpoint com credencial embutida é proibido")
    if (parsed.hostname or "").casefold() != EXPECTED_HOST.casefold():
        raise MaintenanceClientError("endpoint deve apontar para o Desktop governado")
    if parsed.port != EXPECTED_PORT:
        raise MaintenanceClientError("porta do control plane divergente")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise MaintenanceClientError("endpoint base não pode conter path/query/fragment")
    return DEFAULT_ENDPOINT


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
            if not isinstance(decoded, dict):
                raise MaintenanceClientError("resposta do control plane não é objeto JSON")
            return int(response.status), decoded
    except urllib.error.HTTPError as exc:
        try:
            decoded = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {"error": f"http_{exc.code}"}
        return int(exc.code), decoded if isinstance(decoded, dict) else {"error": "invalid_error_payload"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise MaintenanceClientError(f"control plane indisponível: {type(exc).__name__}") from exc


def _worker_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    workers = snapshot.get("workers") or {}
    rows = workers.get("workers") if isinstance(workers, dict) else None
    return [row for row in (rows or []) if isinstance(row, dict)]


def find_desktop_worker(snapshot: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in _worker_rows(snapshot)
        if str(row.get("device_name") or "").casefold() == EXPECTED_HOST.casefold()
    ]
    if len(matches) != 1:
        raise MaintenanceClientError(
            f"worker Desktop deve ser único; encontrados={len(matches)}"
        )
    return matches[0]


def require_worker_capability(
    snapshot: dict[str, Any],
    *,
    task_type: str,
) -> dict[str, Any]:
    worker = find_desktop_worker(snapshot)
    if worker.get("fresh") is not True:
        raise MaintenanceClientError("worker Desktop sem heartbeat fresco")
    if worker.get("eligible") is not True:
        raise MaintenanceClientError("worker Desktop não elegível")
    capabilities = worker.get("capabilities") or {}
    safe_task_types = capabilities.get("safe_task_types") or []
    if not isinstance(safe_task_types, list) or task_type not in safe_task_types:
        raise MaintenanceClientError(
            f"worker Desktop não anuncia capability {task_type}"
        )
    return worker


def get_status(endpoint: str, *, timeout: float = 5.0) -> dict[str, Any]:
    status, payload = request_json("GET", endpoint + "/v1/status", timeout=timeout)
    if status != 200:
        raise MaintenanceClientError(f"status do control plane falhou: HTTP {status}")
    return payload


def build_action(
    action: str,
    *,
    expected_sha: str | None = None,
) -> tuple[str, int, dict[str, Any]]:
    contract = ACTION_CONTRACTS.get(action)
    if contract is None:
        raise MaintenanceClientError("ação não allowlisted")
    payload = dict(contract["payload"])
    if action == "refresh":
        expected = str(expected_sha or "").strip().lower()
        if not SHA_RE.fullmatch(expected):
            raise MaintenanceClientError("refresh exige expected_sha lowercase de 40 caracteres")
        payload["expected_sha"] = expected
    elif expected_sha:
        raise MaintenanceClientError("expected_sha é permitido somente para refresh")
    return str(contract["task_type"]), int(contract["risk"]), payload


def deterministic_identity(action: str, correlation_id: str) -> tuple[str, str]:
    value = str(correlation_id).strip()
    if not value or len(value) > 160:
        raise MaintenanceClientError("correlation_id ausente ou longo demais")
    digest = hashlib.sha256(f"{action}|{value}".encode("utf-8")).hexdigest()[:24]
    return (
        f"evt-desktop-maint-{action}-{digest}",
        f"desktop-maint:{action}:{digest}",
    )



def evaluate_semantic_result(
    action: str,
    result: dict[str, Any],
    *,
    expected_sha: str | None = None,
) -> tuple[bool, str]:
    """Valida efeito funcional local; ausência de testemunho falha fechado."""
    if action == "rdc":
        if result.get("controller_semantic_ok") is True:
            return True, "controller_semantic_ok"
        return False, "controller_semantic_evidence_missing"

    if action == "github-runner":
        state = result.get("after_state")
        if result.get("result") in {"recovered", "already_running"} and state == 4:
            return True, "github_runner_running"
        return False, "github_runner_running_state_not_proven"

    if action == "refresh":
        expected = str(expected_sha or "").strip().lower()
        if (
            SHA_RE.fullmatch(expected)
            and str(result.get("expected_sha") or "").lower() == expected
            and bool(result.get("request"))
        ):
            return True, "refresh_request_persisted"
        return False, "refresh_request_not_proven"

    return False, "semantic_validator_missing"


def submit_action(
    endpoint: str,
    *,
    action: str,
    correlation_id: str,
    expected_sha: str | None = None,
    lease_seconds: int = 60,
    timeout_seconds: float = 60.0,
    request_timeout: float = 5.0,
) -> dict[str, Any]:
    task_type, risk, action_payload = build_action(action, expected_sha=expected_sha)
    snapshot = get_status(endpoint, timeout=request_timeout)
    worker = require_worker_capability(snapshot, task_type=task_type)
    worker_id = str(worker.get("worker_id") or "")
    if not worker_id:
        raise MaintenanceClientError("worker Desktop sem worker_id")

    event_id, idempotency_key = deterministic_identity(action, correlation_id)
    intake = {
        "event_id": event_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "task_type": task_type,
        "payload": action_payload,
        "risk": risk,
        "max_attempts": 2,
        "lease_seconds": lease_seconds,
    }
    status, response = request_json(
        "POST",
        endpoint + "/v1/intake",
        intake,
        timeout=request_timeout,
    )
    if status not in {200, 201}:
        raise MaintenanceClientError(f"intake recusado: HTTP {status}")

    item = response.get("item") or {}
    item_id = str(item.get("id") or "")
    if not item_id:
        raise MaintenanceClientError("intake sem item_id")

    replayed = response.get("replayed") is True
    dispatch = response.get("dispatch")
    if not replayed:
        if not isinstance(dispatch, dict):
            raise MaintenanceClientError("ação criada sem dispatch para o Desktop")
        dispatched_worker = dispatch.get("worker") or {}
        if str(dispatched_worker.get("worker_id") or "") != worker_id:
            raise MaintenanceClientError("dispatch selecionou worker divergente")
        if str(dispatched_worker.get("device_name") or "").casefold() != EXPECTED_HOST.casefold():
            raise MaintenanceClientError("dispatch selecionou host divergente")

    deadline = time.monotonic() + max(1.0, min(float(timeout_seconds), 180.0))
    last_item = item
    while time.monotonic() < deadline:
        status, current = request_json(
            "GET",
            endpoint + f"/v1/work-items/{urllib.parse.quote(item_id, safe='')}",
            timeout=request_timeout,
        )
        if status != 200:
            raise MaintenanceClientError(f"readback do item falhou: HTTP {status}")
        current_item = current.get("item") or {}
        if not isinstance(current_item, dict):
            raise MaintenanceClientError("readback sem item válido")
        last_item = current_item
        if current_item.get("status") in TERMINAL_STATUSES:
            break
        time.sleep(1.0)
    else:
        raise MaintenanceClientError("timeout aguardando estado terminal")

    final_status = str(last_item.get("status") or "")
    result = last_item.get("result") if isinstance(last_item.get("result"), dict) else {}
    queue_completed = final_status == "CONCLUÍDO"
    semantic_ok, semantic_reason = evaluate_semantic_result(
        action,
        result,
        expected_sha=expected_sha,
    )
    evidence = {
        "ok": queue_completed and semantic_ok,
        "queue_completed": queue_completed,
        "semantic_ok": semantic_ok,
        "semantic_reason": semantic_reason,
        "action": action,
        "task_type": task_type,
        "target_host": EXPECTED_HOST,
        "worker_id": worker_id,
        "item_id": item_id,
        "item_status": final_status,
        "replayed": replayed,
        "correlation_id": correlation_id,
        "result": result,
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
    }
    if not queue_completed:
        evidence["last_error"] = last_item.get("last_error")
    elif not semantic_ok:
        evidence["last_error"] = semantic_reason
    return evidence


def status_evidence(snapshot: dict[str, Any]) -> dict[str, Any]:
    worker = find_desktop_worker(snapshot)
    capabilities = worker.get("capabilities") or {}
    return {
        "ok": True,
        "target_host": EXPECTED_HOST,
        "worker": {
            "worker_id": worker.get("worker_id"),
            "device_name": worker.get("device_name"),
            "fresh": worker.get("fresh"),
            "eligible": worker.get("eligible"),
            "profile": worker.get("profile"),
            "controller_version": worker.get("controller_version"),
            "safe_task_types": capabilities.get("safe_task_types", []),
            "last_heartbeat": worker.get("last_heartbeat"),
        },
        "by_status": snapshot.get("by_status", {}),
        "production_touched": False,
        "secrets_read": False,
        "reboot_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manutenção governada do control plane Desktop")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    submit = sub.add_parser("submit")
    submit.add_argument("--action", required=True, choices=sorted(ACTION_CONTRACTS))
    submit.add_argument("--correlation-id", required=True)
    submit.add_argument("--expected-sha")
    submit.add_argument("--lease-seconds", type=int, default=60)
    submit.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        endpoint = validate_endpoint(args.endpoint)
        if args.command == "status":
            payload = status_evidence(get_status(endpoint))
        else:
            payload = submit_action(
                endpoint,
                action=args.action,
                correlation_id=args.correlation_id,
                expected_sha=args.expected_sha,
                lease_seconds=max(10, min(args.lease_seconds, 300)),
                timeout_seconds=args.timeout_seconds,
            )
    except (MaintenanceClientError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "production_touched": False,
                    "secrets_read": False,
                    "reboot_performed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
