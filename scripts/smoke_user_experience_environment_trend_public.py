#!/usr/bin/env python3
"""Smoke público report-only do indicador de tendência ambiental de UX."""
from __future__ import annotations
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone

ENVIRONMENTS = {
    "dev": "https://reqsys-app-dev.fly.dev",
    "stg": "https://reqsys-app-stg.fly.dev",
    "prod": "https://reqsys-app.fly.dev",
}
PATHS = ("/health", "/api/runtime/health", "/api/runtime/readiness", "/api/runtime/liveness")


def fetch(url: str, timeout: int = 15) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"raw": raw[:200]}
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": body}
    except Exception as exc:  # report-only: evidence, not automatic production block
        return {"ok": False, "status": None, "error": type(exc).__name__}


def canonical_fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_report(environments: dict[str, str] | None = None) -> dict:
    environments = environments or ENVIRONMENTS
    results = {}
    for name, base in environments.items():
        checks = {path: fetch(base + path) for path in PATHS}
        passed = sum(1 for check in checks.values() if check["ok"])
        contract = {path: {"ok": value["ok"], "status": value["status"]} for path, value in checks.items()}
        results[name] = {
            "base_url": base,
            "checks": checks,
            "pass_rate": round(passed / len(PATHS) * 100, 2),
            "fingerprint": canonical_fingerprint(contract),
        }
    fingerprints = {value["fingerprint"] for value in results.values()}
    all_healthy = all(value["pass_rate"] == 100 for value in results.values())
    drift = len(fingerprints) > 1
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "indicator": "user_experience_environment_trend",
        "environments": results,
        "availability_rate": round(sum(v["pass_rate"] for v in results.values()) / len(results), 2),
        "drift_detected": drift,
        "status": "UX_ENV_TREND_PUBLIC_OK" if all_healthy and not drift else "UX_ENV_TREND_PUBLIC_REVIEW",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report()
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
