#!/usr/bin/env python3
"""Collect report-only UX/runtime smoke evidence for DEV, STG and PROD."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEGACY_DEV_HOSTS = {"reqsys-app-dev.fly.dev", "reqsys-api-dev.fly.dev"}
REQUIRED_PATHS = (
    "/api/health",
    "/api/runtime/health",
    "/api/runtime/readiness",
    "/api/runtime/liveness",
    "/estatisticas/total-requisitos",
)


def default_environments() -> dict[str, str]:
    dev = os.getenv("REQSYS_DEV_BASE_URL", "").strip().rstrip("/")
    if not dev:
        raise ValueError("REQSYS_DEV_BASE_URL_missing")
    host = urllib.parse.urlparse(dev).hostname or ""
    if host.lower() in LEGACY_DEV_HOSTS or host.lower().endswith(".fly.dev"):
        raise ValueError("legacy_fly_dev_runtime_forbidden")
    return {
        "DEV": dev,
        "STG": "https://reqsys-app-stg.fly.dev",
        "PROD": "https://reqsys-app.fly.dev",
    }


def probe(url: str, timeout: float = 12.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ReqSys-UX-Smoke/1.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            status = int(response.status)
        return {"url": url, "status": status, "ok": 200 <= status < 300,
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
                "body_sha256": hashlib.sha256(body.encode()).hexdigest()}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"url": url, "status": None, "ok": False,
                "latency_ms": round((time.monotonic() - started) * 1000, 2),
                "error": type(exc).__name__}


def collect(environments: dict[str, str], timeout: float = 12.0) -> dict[str, Any]:
    results: dict[str, Any] = {}
    fingerprints: dict[str, str] = {}
    for name, base_url in environments.items():
        checks = [probe(base_url.rstrip("/") + path, timeout) for path in REQUIRED_PATHS]
        canonical = [{"path": REQUIRED_PATHS[i], "status": c["status"], "ok": c["ok"]} for i, c in enumerate(checks)]
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        fingerprints[name] = fingerprint
        results[name] = {
            "base_url": base_url,
            "checks": checks,
            "pass_rate": round(100 * sum(1 for c in checks if c["ok"]) / len(checks), 2),
            "fingerprint": fingerprint,
            "indicator_drilldown_available": next(
                (
                    check["ok"]
                    for path, check in zip(REQUIRED_PATHS, checks, strict=True)
                    if path == "/estatisticas/total-requisitos"
                ),
                False,
            ),
        }
    complete = all(v["pass_rate"] == 100 for v in results.values())
    drift = len(set(fingerprints.values())) > 1
    return {
        "schema_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PUBLIC_UX_ENV_SYNC_OK" if complete and not drift else "PUBLIC_UX_ENV_SYNC_REVIEW",
        "environments": results,
        "environment_coverage": sorted(results),
        "required_paths": list(REQUIRED_PATHS),
        "indicator_drilldown_path": "/estatisticas/total-requisitos",
        "complete": complete,
        "drift_detected": drift,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "automatic_score_promotion": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--environments-json")
    args = parser.parse_args()
    environments = default_environments()
    if args.environments_json:
        environments = json.loads(Path(args.environments_json).read_text(encoding="utf-8"))
    report = collect(environments, args.timeout)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(report["status"])


if __name__ == "__main__":
    main()
