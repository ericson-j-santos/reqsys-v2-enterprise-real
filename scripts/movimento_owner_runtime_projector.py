#!/usr/bin/env python3
"""Projeta telemetria operacional real do ReqSys para owner_movimento.

Somente o dataset fechamento_diario é alimentado neste incremento.
Os três datasets de pendência permanecem vazios até existir fonte com
semântica comprovável para seus campos de negócio.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "reqsys-owner-runtime-projector/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("runtime_payload_invalid")
    return payload


def _relay_request(
    base_url: str,
    token: str,
    method: str,
    route: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + route,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("relay_payload_invalid")
    return value


def build_owner_payload(
    *,
    data_referencia: str,
    health: dict[str, Any],
    runtime: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    health_data = health.get("data") or {}
    runtime_data = runtime.get("data") or {}
    runtime_health = runtime_data.get("runtime_health") or {}
    critical_counts = runtime_data.get("critical_counts") or {}

    metrics = [
        ("reqsys_api_status", health_data.get("status")),
        ("reqsys_runtime_status", runtime_data.get("status")),
        ("reqsys_runtime_status_raw", runtime_data.get("status_raw")),
        ("reqsys_runtime_risk_score", runtime_data.get("risk_score")),
        ("reqsys_runtime_uptime_seconds", int(float(runtime_data.get("uptime_seconds") or 0))),
        ("reqsys_runtime_score_global", runtime_health.get("score_global")),
        ("reqsys_runtime_pending_items", critical_counts.get("pending_items")),
        ("reqsys_runtime_blocked_items", critical_counts.get("blocked_items")),
    ]

    observation = (
        "Fonte: runtime local ReqSys DEV; captura owner-managed; "
        "não representa transação comercial."
    )
    fechamento: list[dict[str, Any]] = []
    for name, value in metrics:
        if value is None:
            raise RuntimeError(f"runtime_metric_missing:{name}")
        fechamento.append(
            {
                "indicador": name,
                "valor": str(value),
                "observacao": observation,
                "data_referencia": data_referencia,
            }
        )

    return {
        "correlation_id": correlation_id,
        "data_referencia": data_referencia,
        "datasets": {
            "fechamento_diario": fechamento,
            "pendencias_cadastro": [],
            "pendencias_historicas": [],
            "pendencias_observacao": [],
        },
    }


def submit_ingest(
    *,
    relay_url: str,
    relay_token: str,
    payload: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    queued = _relay_request(
        relay_url,
        relay_token,
        "POST",
        "/submit",
        {"operation": "ingest", "payload": payload},
    )
    request_id = str(queued.get("id") or "")
    if not request_id:
        raise RuntimeError("relay_request_id_missing")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = _relay_request(
            relay_url,
            relay_token,
            "GET",
            "/result?id=" + urllib.parse.quote(request_id),
            timeout=5.0,
        )
        if result.get("status") == "done":
            actual = result.get("result")
            if not isinstance(actual, dict):
                raise RuntimeError("relay_result_invalid")
            return actual
        time.sleep(0.5)
    raise TimeoutError("relay_timeout")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-referencia", required=True)
    parser.add_argument("--runtime-base", default="http://127.0.0.1:8081")
    parser.add_argument("--relay", default="http://127.0.0.1:18444")
    parser.add_argument("--relay-token-file", type=Path, required=True)
    parser.add_argument("--correlation-id", default="owner-runtime-projector")
    args = parser.parse_args()

    token = args.relay_token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("relay_token_invalid")

    health = _get_json(args.runtime_base.rstrip("/") + "/api/health")
    runtime = _get_json(args.runtime_base.rstrip("/") + "/api/runtime/health")
    payload = build_owner_payload(
        data_referencia=args.data_referencia,
        health=health,
        runtime=runtime,
        correlation_id=args.correlation_id,
    )
    actual = submit_ingest(
        relay_url=args.relay,
        relay_token=token,
        payload=payload,
    )

    evidence = {
        "status": actual.get("status"),
        "source_authority": actual.get("source_authority"),
        "data_referencia": actual.get("data_referencia"),
        "row_counts": actual.get("row_counts"),
        "write_count": actual.get("write_count"),
        "runtime_metrics_projected": len(payload["datasets"]["fechamento_diario"]),
        "synthetic": False,
        "business_transaction_claimed": False,
        "production_touched": False,
    }
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if actual.get("status") in {"applied", "noop"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
