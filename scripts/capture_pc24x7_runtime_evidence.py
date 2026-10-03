#!/usr/bin/env python3
"""Captura evidência fail-closed do runtime DEV executado no PC24x7.

Este script é executado no próprio host PC24x7, fora do GitHub Actions. Ele
valida os endpoints locais do gateway e registra o SHA do checkout que produziu
a evidência. A evidência só fica pronta quando todos os probes obrigatórios
respondem 2xx e, se informado, o SHA esperado coincide com o checkout local.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://localhost:8081"
REQUIRED_ENDPOINTS = ("/api/health", "/api/runtime/health")


def current_git_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def probe(base_url: str, endpoint: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    started = time.perf_counter()
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "reqsys-pc24x7-evidence/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - destino local explícito
            raw = response.read(262_144)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = None
            return {
                "endpoint": endpoint,
                "url": url,
                "ok": 200 <= int(response.status) < 300,
                "status_code": int(response.status),
                "elapsed_ms": elapsed_ms,
                "payload": payload if isinstance(payload, dict) else None,
                "error": None,
            }
    except HTTPError as exc:
        return {
            "endpoint": endpoint,
            "url": url,
            "ok": False,
            "status_code": int(exc.code),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "payload": None,
            "error": str(exc),
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "endpoint": endpoint,
            "url": url,
            "ok": False,
            "status_code": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_evidence(
    *,
    source_commit: str,
    expected_sha: str | None,
    base_url: str,
    results: list[dict[str, Any]],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    runtime_ready = bool(results) and all(bool(item.get("ok")) for item in results)
    same_sha = expected_sha is None or source_commit == expected_sha
    return {
        "schema_version": "1.0.0",
        "contract": "pc24x7-dev-runtime-evidence",
        "provider": "pc24x7",
        "environment": "dev",
        "generated_at": timestamp.astimezone(UTC).isoformat(),
        "base_url": base_url.rstrip("/"),
        "source_commit": source_commit,
        "expected_sha": expected_sha,
        "same_sha": same_sha,
        "runtime_ready": runtime_ready,
        "ready": runtime_ready and same_sha,
        "required_endpoints": list(REQUIRED_ENDPOINTS),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura evidência do runtime DEV no PC24x7")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--expected-sha")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/runtime/pc24x7-dev-runtime-evidence.json"),
    )
    args = parser.parse_args()

    source_commit = current_git_sha(args.repo_root)
    results = [probe(args.base_url, endpoint, args.timeout) for endpoint in REQUIRED_ENDPOINTS]
    evidence = build_evidence(
        source_commit=source_commit,
        expected_sha=args.expected_sha,
        base_url=args.base_url,
        results=results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
