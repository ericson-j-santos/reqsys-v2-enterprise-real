#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_SOURCE_HOST = "Noteri"
TARGET_HOST = "DESKTOP-PDQK954"
PROBES = {
    8081: ["/healthz", "/readyz", "/status"],
    8083: ["/healthz", "/readyz", "/status"],
    8097: ["/health", "/readyz"],
    8787: ["/readyz", "/healthz", "/v1/workers"],
}


def tcp_probe(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(host: str, port: int, path: str, timeout: float = 2.0) -> dict:
    req = Request(
        f"http://{host}:{port}{path}",
        method="GET",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(4096).decode("utf-8", errors="replace")
            return {
                "path": path,
                "status": int(response.status),
                "content_type": str(response.headers.get("Content-Type") or "")[:120],
                "body_prefix": raw[:500],
            }
    except HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", errors="replace")
        return {
            "path": path,
            "status": int(exc.code),
            "content_type": str(exc.headers.get("Content-Type") or "")[:120],
            "body_prefix": raw[:500],
        }
    except (URLError, OSError, TimeoutError) as exc:
        return {"path": path, "error_type": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()

    source_host = socket.gethostname()
    if source_host.casefold() != EXPECTED_SOURCE_HOST.casefold():
        raise SystemExit("source_host_not_authorized")

    started = time.time()
    results = []
    for port, paths in PROBES.items():
        open_tcp = tcp_probe(TARGET_HOST, port)
        item = {"port": port, "tcp_open": open_tcp, "http": []}
        if open_tcp:
            for path in paths:
                item["http"].append(http_probe(TARGET_HOST, port, path))
        results.append(item)

    payload = {
        "schema_version": 1,
        "correlation_id": args.correlation_id,
        "source_host": source_host,
        "target_host": TARGET_HOST,
        "probe_scope": sorted(PROBES),
        "results": results,
        "duration_seconds": round(time.time() - started, 3),
        "mutation_performed": False,
        "remote_shell_used": False,
        "production_touched": False,
        "secrets_read": False,
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
