#!/usr/bin/env python3
"""Executa o ciclo horário governado do TODO Global via Runtime ReqSys."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TERMINAL_SUCCESS = {"completed"}
TERMINAL_FAILURE = {"failed", "dead_letter"}
IDEMPOTENCY_KEY = hashlib.sha256(
    b"global|Automacao|todo-global-hourly-reconciliation"
).hexdigest()


def build_event(run_id: str, run_attempt: str, occurred_at: datetime | None = None) -> dict[str, Any]:
    now = occurred_at or datetime.now(timezone.utc)
    correlation_id = f"todo-global-hourly-{run_id}-{run_attempt}"
    return {
        "schema_version": "1.0",
        "event_id": correlation_id,
        "event_type": "todo.reconcile.requested",
        "occurred_at": now.astimezone(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "idempotency_key": IDEMPOTENCY_KEY,
        "project": "Global",
        "producer": "github-actions",
        "todo": {
            "title": "Reconciliar TODO Global e projeções",
            "type": "Automação",
            "external_id": "todo-global-hourly-reconciliation",
            "status": "EM ANDAMENTO",
            "priority": "P1",
            "next_action": "Reconciliar fonte canônica, projeções e itens executáveis.",
            "completion_criteria": "Ciclo terminal com leitura independente e replay idempotente.",
            "evidence": f"GitHub Actions run {run_id}, tentativa {run_attempt}.",
            "evidence_url": (
                f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{run_id}"
            ),
            "e2e_status": "PENDENTE",
            "origin": "GitHub Actions",
            "origin_url": (
                f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{run_id}"
            ),
            "source": "github-actions",
        },
    }


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str = "",
    timeout: float = 30,
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if token:
        headers["X-Service-Token"] = token
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return exc.code, parsed


def assert_negative_control(endpoint: str, token: str) -> None:
    status, _ = request_json(
        "POST",
        endpoint,
        payload={"schema_version": "invalid"},
        token=token,
    )
    if status not in {400, 422}:
        raise RuntimeError(f"controle_negativo_nao_rejeitado: http_status={status}")


def submit(endpoint: str, event: dict[str, Any], token: str) -> dict[str, Any]:
    status, body = request_json("POST", endpoint, payload=event, token=token)
    if status not in {200, 202}:
        raise RuntimeError(f"evento_nao_aceito: http_status={status}")
    for key in ("event_id", "job_id", "correlation_id", "idempotency_key", "status_url"):
        if not body.get(key):
            raise RuntimeError(f"resposta_sem_{key}")
    if body["event_id"] != event["event_id"]:
        raise RuntimeError("event_id_divergente")
    if body["correlation_id"] != event["correlation_id"]:
        raise RuntimeError("correlation_id_divergente")
    if body["idempotency_key"] != event["idempotency_key"]:
        raise RuntimeError("idempotency_key_divergente")
    return body


def resolve_runtime_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def wait_terminal(
    base_url: str,
    status_url: str,
    token: str,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    resolved = resolve_runtime_url(base_url, status_url)
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, last = request_json("GET", resolved, token=token)
        if status != 200:
            raise RuntimeError(f"status_readback_falhou: http_status={status}")
        state = str(last.get("status", ""))
        if state in TERMINAL_SUCCESS:
            result = last.get("resultado") or {}
            if result.get("readback_verified") is not True:
                raise RuntimeError("conclusao_sem_readback_independente")
            return last
        if state in TERMINAL_FAILURE:
            raise RuntimeError(f"estado_terminal_falhou:{state}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"timeout_sem_estado_terminal:last={last.get('status')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", default="1")
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    token = os.environ.get("TODO_GLOBAL_RUNTIME_TOKEN", "")
    endpoint = args.runtime_url.rstrip("/") + "/api/todo-events"
    event = build_event(args.run_id, args.run_attempt)

    assert_negative_control(endpoint, token)
    accepted = submit(endpoint, event, token)
    terminal = wait_terminal(
        args.runtime_url,
        accepted["status_url"],
        token,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    replay = submit(endpoint, event, token)
    if replay["job_id"] != accepted["job_id"]:
        raise RuntimeError("replay_criou_segundo_job")
    if replay.get("duplicate_event") is not True:
        raise RuntimeError("replay_nao_sinalizou_duplicidade")

    evidence = {
        "result": "TODO_GLOBAL_HOURLY_CYCLE_VALIDATED",
        "event_id": event["event_id"],
        "correlation_id": event["correlation_id"],
        "idempotency_key": event["idempotency_key"],
        "job_id": accepted["job_id"],
        "terminal_status": terminal["status"],
        "readback_verified": True,
        "replay_duplicate_event": True,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
