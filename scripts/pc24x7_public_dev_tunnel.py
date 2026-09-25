#!/usr/bin/env python3
"""Reconcilia a exposição pública DEV do ReqSys no PC24x7.

Mantém dois Cloudflare Quick Tunnels apontando para o gateway DEV local via
host.docker.internal:8083. O uso de host.docker.internal evita drift quando o
IPv4 LAN do host muda. Não lê nem grava segredos.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TUNNELS = ("reqsys-dev-gateway-tunnel", "reqsys-dev-failover-tunnel")
DEFAULT_IMAGE = "cloudflare/cloudflared:latest"
DEFAULT_TARGET = "http://host.docker.internal:8083"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)


def run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def extract_quick_urls(text: str) -> list[str]:
    seen: list[str] = []
    for url in URL_RE.findall(text or ""):
        if url not in seen:
            seen.append(url)
    return seen


def inspect_container(name: str) -> dict[str, Any] | None:
    completed = run(["docker", "inspect", name])
    if completed.returncode != 0:
        return None
    payload = json.loads(completed.stdout)[0]
    return {
        "name": name,
        "running": bool((payload.get("State") or {}).get("Running")),
        "args": list(payload.get("Args") or []),
        "restart": ((payload.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name"),
        "image": (payload.get("Config") or {}).get("Image"),
    }


def container_matches(state: dict[str, Any] | None, *, target: str, image: str) -> bool:
    if not state:
        return False
    return (
        state.get("running") is True
        and target in (state.get("args") or [])
        and state.get("restart") == "unless-stopped"
        and state.get("image") == image
    )


def build_run_command(name: str, *, target: str, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "-d",
        "--name",
        name,
        "--restart",
        "unless-stopped",
        image,
        "tunnel",
        "--url",
        target,
    ]


def probe(url: str, timeout: float = 8.0) -> dict[str, Any]:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "ReqSysPC24x7PublicRuntime/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": True,
                "status": int(response.status),
                "content_type": response.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": int(exc.code), "error": repr(exc)}
    except (OSError, urllib.error.URLError) as exc:
        return {"ok": False, "error": repr(exc)}


def state_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".reqsys"
    return root / "ReqSys" / "PublicRuntime" / "dev-tunnels.json"


def reconcile_one(name: str, *, target: str, image: str, apply: bool) -> dict[str, Any]:
    before = inspect_container(name)
    changed = False
    if not container_matches(before, target=target, image=image):
        if not apply:
            return {"name": name, "changed": False, "before": before, "ready": False}
        if before is not None:
            removed = run(["docker", "rm", "-f", name])
            if removed.returncode != 0:
                raise RuntimeError(f"falha removendo {name}: {removed.stderr.strip()}")
        started = run(build_run_command(name, target=target, image=image))
        if started.returncode != 0:
            raise RuntimeError(f"falha iniciando {name}: {started.stderr.strip()}")
        changed = True

    deadline = time.monotonic() + 35.0
    url = None
    while time.monotonic() < deadline:
        logs = run(["docker", "logs", "--tail", "120", name], timeout=10)
        urls = extract_quick_urls(f"{logs.stdout}\n{logs.stderr}")
        if urls:
            url = urls[-1]
            break
        time.sleep(1.0)

    after = inspect_container(name)
    health = probe(f"{url}/api/health") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    runtime_health = probe(f"{url}/api/runtime/health") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    runtime_readiness = probe(f"{url}/api/runtime/readiness") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    build_info = probe(f"{url}/api/runtime/build-info") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    task_console = probe(f"{url}/task-console") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    vite_client = probe(f"{url}/@vite/client") if url else {"ok": False, "error": "quick_tunnel_url_missing"}
    ready = (
        container_matches(after, target=target, image=image)
        and bool(url)
        and health.get("status") == 200
        and runtime_health.get("status") == 200
        and runtime_readiness.get("status") == 200
        and build_info.get("status") == 200
        and task_console.get("status") == 200
        and vite_client.get("status") == 404
    )
    return {
        "name": name,
        "changed": changed,
        "before": before,
        "after": after,
        "url": url,
        "health": health,
        "runtime_health": runtime_health,
        "runtime_readiness": runtime_readiness,
        "build_info": build_info,
        "task_console": task_console,
        "vite_client": vite_client,
        "ready": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcilia Quick Tunnels DEV do ReqSys")
    parser.add_argument("--apply", action="store_true", help="aplica correções; sem esta flag é somente leitura")
    parser.add_argument("--target", default=os.environ.get("REQSYS_DEV_TUNNEL_TARGET", DEFAULT_TARGET))
    parser.add_argument("--image", default=os.environ.get("REQSYS_DEV_TUNNEL_IMAGE", DEFAULT_IMAGE))
    parser.add_argument("--state-file", type=Path, default=state_path())
    args = parser.parse_args()

    results = [
        reconcile_one(name, target=args.target, image=args.image, apply=args.apply)
        for name in TUNNELS
    ]
    payload = {
        "schema_version": "1.0.0",
        "environment": "dev",
        "provider": "cloudflare_quick_tunnel",
        "target": args.target,
        "image": args.image,
        "apply": args.apply,
        "ready": all(item.get("ready") for item in results),
        "tunnels": results,
    }
    args.state_file.parent.mkdir(parents=True, exist_ok=True)
    args.state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
