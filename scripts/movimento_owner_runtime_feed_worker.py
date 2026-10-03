#!/usr/bin/env python3
"""Worker persistente: Desktop ReqSys runtime -> Owner Gateway local no Noteri."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any


def load_projector(path: Path):
    spec = importlib.util.spec_from_file_location("movimento_owner_runtime_projector_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("projector_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_json(
    url: str,
    *,
    method: str,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("owner_gateway_payload_invalid")
    return value


def run_once(config: dict[str, Any], projector) -> dict[str, Any]:
    runtime_base = str(config["runtime_base"]).rstrip("/")
    owner_config = json.loads(Path(config["owner_config"]).read_text(encoding="utf-8"))
    owner_token = Path(config["owner_token_file"]).read_text(encoding="utf-8").strip()
    if len(owner_token) < 32:
        raise RuntimeError("owner_token_invalid")
    owner_base = f"http://{owner_config['bind_ip']}:{int(owner_config['port'])}"

    ref = date.today().isoformat()
    health = projector._get_json(runtime_base + "/api/health")
    runtime = projector._get_json(runtime_base + "/api/runtime/health")
    payload = projector.build_owner_payload(
        data_referencia=ref,
        health=health,
        runtime=runtime,
        correlation_id=f"owner-runtime-feed-{ref}",
    )

    ingest = request_json(
        owner_base + "/ingest",
        method="POST",
        token=owner_token,
        payload=payload,
    )
    if ingest.get("status") not in {"applied", "noop"}:
        raise RuntimeError("owner_ingest_failed")

    sync = request_json(
        owner_base + "/sync",
        method="POST",
        token=owner_token,
        payload={"data_referencia": ref},
    )
    if sync.get("status") not in {"applied", "noop"}:
        raise RuntimeError("owner_sync_failed")

    return {
        "status": "passed",
        "data_referencia": ref,
        "ingest_status": ingest.get("status"),
        "sync_status": sync.get("status"),
        "row_counts": sync.get("row_counts"),
        "write_count": sync.get("write_count"),
        "runtime_metrics_projected": len(payload["datasets"]["fechamento_diario"]),
        "synthetic": False,
        "business_transaction_claimed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--projector", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    interval = int(config.get("interval_seconds", 900))
    if interval < 300:
        raise SystemExit("interval_too_short")
    projector = load_projector(args.projector)

    while True:
        try:
            result = run_once(config, projector)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "error": type(exc).__name__,
                        "production_touched": False,
                    }
                ),
                flush=True,
            )
            if args.once:
                return 3
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
