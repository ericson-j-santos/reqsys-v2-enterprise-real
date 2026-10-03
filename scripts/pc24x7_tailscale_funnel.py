#!/usr/bin/env python3
"""Reconcilia Tailscale Funnel para o ReqSys DEV no PC24x7.

Publica o gateway local DEV (:8083) em HTTPS usando o hostname estável do nó
Tailscale (*.ts.net). Não lê nem grava credenciais.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TARGET = "8083"


def run(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def tailscale_status() -> dict[str, Any]:
    completed = run(["tailscale", "status", "--json"])
    if completed.returncode != 0:
        raise RuntimeError(f"tailscale status falhou: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def stable_url(status: dict[str, Any]) -> str:
    dns_name = str(((status.get("Self") or {}).get("DNSName") or "")).strip().rstrip(".")
    if not dns_name:
        raise RuntimeError("DNSName Tailscale ausente")
    return f"https://{dns_name}"


def funnel_status() -> dict[str, Any]:
    completed = run(["tailscale", "funnel", "status"])
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def probe(url: str, timeout: float = 10.0) -> dict[str, Any]:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "ReqSysTailscaleFunnel/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": True,
                "status": int(response.status),
                "content_type": response.headers.get("Content-Type"),
            }
    except (OSError, urllib.error.URLError) as exc:
        return {"ok": False, "error": repr(exc)}


def apply_funnel(target: str) -> dict[str, Any]:
    before = funnel_status()
    completed = run(["tailscale", "funnel", "--bg", "--yes", target], timeout=90)
    result = {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0:
        return {"ok": False, "before": before, "apply": result}
    after = funnel_status()
    return {"ok": True, "before": before, "apply": result, "after": after}


def main() -> int:
    parser = argparse.ArgumentParser(description="ReqSys DEV via Tailscale Funnel")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    args = parser.parse_args()

    status = tailscale_status()
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "provider": "tailscale_funnel",
        "backend_state": status.get("BackendState"),
        "magic_dns_enabled": bool((status.get("CurrentTailnet") or {}).get("MagicDNSEnabled")),
        "stable_url": stable_url(status),
        "target": args.target,
        "apply": args.apply,
        "funnel_before": funnel_status(),
    }

    if payload["backend_state"] != "Running" or not payload["magic_dns_enabled"]:
        payload["ready"] = False
        payload["error"] = "tailscale_not_ready"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    if args.apply:
        applied = apply_funnel(args.target)
        payload["reconcile"] = applied
        if not applied.get("ok"):
            payload["ready"] = False
            payload["error"] = "funnel_apply_failed"
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 3

    payload["funnel_after"] = funnel_status()
    payload["health"] = probe(payload["stable_url"] + "/api/health")
    payload["task_console"] = probe(payload["stable_url"] + "/task-console")
    payload["ready"] = (
        payload["health"].get("status") == 200
        and payload["task_console"].get("status") == 200
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ready"] else 4


if __name__ == "__main__":
    sys.exit(main())
