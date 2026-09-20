#!/usr/bin/env python3
"""Supervisor idempotente do runtime público DEV no PC24x7.

Mantém o gateway local e os transportes públicos reconciliados sem interação
humana repetitiva. O consentimento inicial do Tailscale Funnel é tratado como
bloqueio externo: enquanto a capability não existir, Cloudflare Quick Tunnel
permanece ativo e o supervisor não abre navegador em loop.
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
TAILSCALE_FUNNEL = ROOT / "scripts" / "pc24x7_tailscale_funnel.py"
LOCAL_GATEWAY = "http://127.0.0.1:8083"
CONTAINERS = ("reqsys-live-api-1", "reqsys-live-frontend-1", "reqsys-live-nginx-1")


def run(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
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
        req = urllib.request.Request(url, headers={"User-Agent": "ReqSysDevSupervisor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"ok": True, "status": int(response.status)}
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


def tailscale_capabilities() -> dict[str, Any]:
    status = run(["tailscale", "status", "--json"], timeout=20)
    if status.returncode != 0:
        return {"ready": False, "error": status.stderr.strip()}
    data = json.loads(status.stdout)
    cap_map = (data.get("Self") or {}).get("CapMap") or {}
    keys = sorted(str(key) for key in cap_map)
    funnel_allowed = any("funnel" in key.casefold() for key in keys)
    return {
        "ready": data.get("BackendState") == "Running",
        "magic_dns": bool((data.get("CurrentTailnet") or {}).get("MagicDNSEnabled")),
        "funnel_allowed": funnel_allowed,
        "dns_name": str((data.get("Self") or {}).get("DNSName") or "").rstrip("."),
    }


def run_json_script(path: Path, *args: str, timeout: int = 120) -> dict[str, Any]:
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
            payload["stdout_tail"] = completed.stdout[-2000:]
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
        "schema_version": "1.0.0",
        "environment": "dev",
        "apply": args.apply,
        "timestamp_epoch": int(time.time()),
    }

    payload["local_before"] = {
        "frontend": probe(LOCAL_GATEWAY + "/task-console"),
        "health": probe(LOCAL_GATEWAY + "/api/health"),
    }
    if args.apply:
        payload["runtime"] = ensure_containers()
    else:
        payload["runtime"] = {"changed": False}

    payload["local_after"] = {
        "frontend": probe(LOCAL_GATEWAY + "/task-console"),
        "health": probe(LOCAL_GATEWAY + "/api/health"),
    }

    if args.apply:
        payload["cloudflare"] = run_json_script(PUBLIC_TUNNEL, "--apply")
    else:
        payload["cloudflare"] = run_json_script(PUBLIC_TUNNEL)

    tailscale = tailscale_capabilities()
    payload["tailscale_capabilities"] = tailscale
    if tailscale.get("ready") and tailscale.get("magic_dns") and tailscale.get("funnel_allowed"):
        payload["tailscale"] = run_json_script(
            TAILSCALE_FUNNEL,
            *(("--apply",) if args.apply else ()),
        )
        payload["human_blocker"] = None
    else:
        payload["tailscale"] = {
            "deferred": True,
            "reason": "funnel_consent_required" if not tailscale.get("funnel_allowed") else "tailscale_not_ready",
        }
        payload["human_blocker"] = (
            "TAILSCALE_FUNNEL_CONSENT_REQUIRED" if not tailscale.get("funnel_allowed") else "TAILSCALE_NOT_READY"
        )

    payload["ready"] = (
        payload["local_after"]["frontend"].get("status") == 200
        and payload["local_after"]["health"].get("status") == 200
        and (payload.get("cloudflare", {}).get("result") or {}).get("ready") is True
    )

    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
