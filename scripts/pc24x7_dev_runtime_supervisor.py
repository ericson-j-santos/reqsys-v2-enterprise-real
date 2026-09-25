#!/usr/bin/env python3
"""Supervisor idempotente do runtime público DEV no PC24x7.

Mantém containers, Cloudflare Quick Tunnels e o locator público assinado.
Política econômica: custo adicional zero; Tailscale, DuckDNS e NPort não
fazem parte da rota crítica.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TUNNEL = ROOT / "scripts" / "pc24x7_public_dev_tunnel.py"
LOCATOR_PUBLISHER = ROOT / "scripts" / "pc24x7_dev_locator_publisher.py"
LOCAL_GATEWAY = "http://127.0.0.1:8083"
CONTAINERS = ("reqsys-live-api-1", "reqsys-live-frontend-1", "reqsys-live-nginx-1")


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def probe(url: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ReqSysDevSupervisor/2.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": True, "status": int(response.status)}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": int(exc.code), "error": repr(exc)}
    except (OSError, urllib.error.URLError) as exc:
        return {"ok": False, "error": repr(exc)}


def ensure_containers() -> dict[str, Any]:
    results = []
    changed = False
    for name in CONTAINERS:
        inspect = run(["docker", "inspect", "-f", "{{.State.Running}}", name], timeout=15)
        running = inspect.returncode == 0 and inspect.stdout.strip().lower() == "true"
        item = {"name": name, "running_before": running}
        if not running:
            started = run(["docker", "start", name], timeout=30)
            item["start_returncode"] = started.returncode
            item["start_stderr"] = started.stderr.strip()
            changed = changed or started.returncode == 0
        verify = run(["docker", "inspect", "-f", "{{.State.Running}}", name], timeout=15)
        item["running_after"] = verify.returncode == 0 and verify.stdout.strip().lower() == "true"
        results.append(item)
    return {"changed": changed, "containers": results, "ready": all(x["running_after"] for x in results)}


def run_json_script(path: Path, *args: str, timeout: int = 150) -> dict[str, Any]:
    completed = run([sys.executable, str(path), *args], timeout=timeout)
    payload: dict[str, Any] = {
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip(),
    }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if lines:
        try:
            payload["result"] = json.loads(lines[-1])
        except json.JSONDecodeError:
            payload["stdout_tail"] = completed.stdout[-3000:]
    return payload


def state_file() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home()
    return base / "ReqSys" / "PublicRuntime" / "dev-supervisor.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Supervisor ReqSys DEV no PC24x7")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "schema_version": "2.0.0",
        "environment": "dev",
        "apply": args.apply,
        "timestamp_epoch": int(time.time()),
        "cost_policy": "zero_additional_cost",
        "transport": "cloudflare_quick_tunnel",
        "locator": "github_pages_plus_signed_ntfy",
    }

    payload["local_before"] = {
        "frontend": probe(LOCAL_GATEWAY + "/task-console"),
        "health": probe(LOCAL_GATEWAY + "/api/health"),
        "runtime_health": probe(LOCAL_GATEWAY + "/api/runtime/health"),
        "runtime_readiness": probe(LOCAL_GATEWAY + "/api/runtime/readiness"),
        "build_info": probe(LOCAL_GATEWAY + "/api/runtime/build-info"),
        "vite_client": probe(LOCAL_GATEWAY + "/@vite/client"),
    }
    payload["runtime"] = ensure_containers() if args.apply else {"changed": False}
    payload["local_after"] = {
        "frontend": probe(LOCAL_GATEWAY + "/task-console"),
        "health": probe(LOCAL_GATEWAY + "/api/health"),
        "runtime_health": probe(LOCAL_GATEWAY + "/api/runtime/health"),
        "runtime_readiness": probe(LOCAL_GATEWAY + "/api/runtime/readiness"),
        "build_info": probe(LOCAL_GATEWAY + "/api/runtime/build-info"),
        "vite_client": probe(LOCAL_GATEWAY + "/@vite/client"),
    }

    local_ready = (
        all(
            payload["local_after"][key].get("status") == 200
            for key in ("frontend", "health", "runtime_health", "runtime_readiness", "build_info")
        )
        and payload["local_after"]["vite_client"].get("status") == 404
    )

    payload["cloudflare"] = run_json_script(
        PUBLIC_TUNNEL,
        *(("--apply",) if args.apply else ()),
    )

    if args.apply and local_ready:
        payload["public_locator"] = run_json_script(LOCATOR_PUBLISHER)
    elif args.apply:
        payload["public_locator"] = {
            "deferred": True,
            "reason": "local_runtime_contract_failed",
        }
    else:
        payload["public_locator"] = {"deferred": True}

    cloudflare_ready = (payload.get("cloudflare", {}).get("result") or {}).get("ready") is True
    locator_result = payload.get("public_locator", {}).get("result") or {}
    locator_ready = (
        locator_result.get("published") is True
        and int(locator_result.get("healthy_url_count") or 0) > 0
    )
    payload["local_runtime_contract_ready"] = local_ready
    payload["locator_ready"] = locator_ready
    payload["human_blocker"] = None
    payload["ready"] = local_ready and cloudflare_ready and (locator_ready if args.apply else True)

    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
