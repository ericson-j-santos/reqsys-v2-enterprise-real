#!/usr/bin/env python3
"""Poll public /api/runtime/build-info until build_sha matches expected deploy SHA."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def normalize_sha(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"([0-9a-f]{7,40})", value.strip(), flags=re.IGNORECASE)
    return match.group(1)[:12] if match else value.strip()[:12]


def fetch_build_info(base_url: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    url = f"{base_url.rstrip('/')}/api/runtime/build-info"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "reqsys-deploy-verify/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, str(exc)
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        return data, None
    return payload if isinstance(payload, dict) else None, "invalid_payload"


def verify_deploy_build_sha(
    *,
    base_url: str,
    expected_sha: str,
    timeout: float,
    max_attempts: int,
    delay_seconds: float,
) -> dict[str, Any]:
    expected = normalize_sha(expected_sha) or expected_sha
    attempts: list[dict[str, Any]] = []
    observed: str | None = None
    for attempt in range(1, max_attempts + 1):
        info, error = fetch_build_info(base_url, timeout)
        observed_raw = (info or {}).get("build_sha") or (info or {}).get("commit_sha")
        observed = normalize_sha(str(observed_raw) if observed_raw else None)
        matched = observed == expected
        attempts.append(
            {
                "attempt": attempt,
                "observed_sha": observed_raw,
                "observed_sha_normalized": observed,
                "matched": matched,
                "error": error,
            }
        )
        if matched:
            return {
                "ok": True,
                "expected_sha": expected,
                "observed_sha": observed_raw,
                "attempts": attempt,
                "history": attempts,
            }
        if attempt < max_attempts:
            time.sleep(delay_seconds)
    return {
        "ok": False,
        "expected_sha": expected,
        "observed_sha": observed,
        "attempts": len(attempts),
        "history": attempts,
        "detail": f"build_sha não convergiu para {expected} (último observado: {observed})",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployed Fly build_sha matches expected SHA")
    parser.add_argument("--base-url", default="https://reqsys-api.fly.dev")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=15.0)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = verify_deploy_build_sha(
        base_url=args.base_url,
        expected_sha=args.expected_sha,
        timeout=args.timeout,
        max_attempts=args.max_attempts,
        delay_seconds=args.delay_seconds,
    )
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
