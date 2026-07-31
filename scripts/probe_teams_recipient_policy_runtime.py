#!/usr/bin/env python3
"""Probe the Teams recipient-policy endpoint without sending a real message."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://reqsys-api.fly.dev"
DEFAULT_POLICIES = ("hitl-approvers", "reqsys-operations")


def _safe_detail(value: str, limit: int = 300) -> str:
    return " ".join(value.replace("\x00", " ").split())[:limit]


def probe_policy(
    *,
    base_url: str,
    policy: str,
    timeout: float = 20.0,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    normalized_policy = policy.strip().lower()
    if not normalized_policy:
        raise ValueError("policy is required")

    endpoint = (
        f"{base_url.rstrip('/')}/v1/teams-gateway/recipient-policies/"
        f"{quote(normalized_policy, safe='')}/messages"
    )
    payload = {
        "destino_tipo": "auto",
        "modo": "auto",
        "destino_id": None,
        "texto": "ReqSys recipient-policy readiness probe",
        "autor": "reqsys-readiness",
        "permitir_fallback": False,
        "dry_run": True,
        "delivery_mode": "first_success",
        "metadata": {"titulo": "ReqSys Teams policy readiness", "probe": True},
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "reqsys-teams-policy-readiness/1.1",
        },
    )

    status_code: int | None = None
    response_payload: Any = None
    error: str | None = None
    detail: str | None = None
    try:
        with opener(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", 200))
            raw = response.read().decode("utf-8", errors="replace")
            response_payload = json.loads(raw) if raw.strip() else {}
    except HTTPError as exc:
        status_code = int(exc.code)
        error = f"http_{exc.code}"
        detail = _safe_detail(exc.read().decode("utf-8", errors="replace"))
    except (URLError, TimeoutError) as exc:
        error = "network_error"
        detail = _safe_detail(str(exc))
    except json.JSONDecodeError as exc:
        error = "json_invalid"
        detail = _safe_detail(str(exc))

    endpoint_available = bool(
        status_code is not None
        and 200 <= status_code < 300
        and isinstance(response_payload, dict)
    )
    data = response_payload.get("data") if isinstance(response_payload, dict) else None
    dry_run_confirmed = bool(isinstance(data, dict) and data.get("dry_run") is True)
    policy_ready = endpoint_available and dry_run_confirmed

    return {
        "policy": normalized_policy,
        "endpoint_available": endpoint_available,
        "dry_run_confirmed": dry_run_confirmed,
        "policy_ready": policy_ready,
        "status_code": status_code,
        "error": error,
        "detail": detail,
        "legacy_fallback_required": not policy_ready,
        "fallback_retirement_candidate": policy_ready,
        "production_touched": False,
    }


def build_report(
    *,
    base_url: str,
    policies: list[str],
    timeout: float = 20.0,
    opener: Callable[..., Any] = urlopen,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    unique_policies = list(
        dict.fromkeys(policy.strip().lower() for policy in policies if policy.strip())
    )
    if not unique_policies:
        raise ValueError("at least one policy is required")

    results = [
        probe_policy(base_url=base_url, policy=policy, timeout=timeout, opener=opener)
        for policy in unique_policies
    ]
    available = sum(1 for item in results if item["endpoint_available"])
    confirmed = sum(1 for item in results if item["dry_run_confirmed"])
    ready = sum(1 for item in results if item["policy_ready"])
    all_ready = ready == len(results)
    return {
        "schema_version": "1.1.0",
        "contract": "teams-recipient-policy-runtime-readiness",
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "base_url": base_url.rstrip("/"),
        "summary": {
            "policies_checked": len(results),
            "endpoint_available": available,
            "dry_run_confirmed": confirmed,
            "ready_policies": ready,
            "legacy_fallback_required": len(results) - ready,
            "all_policies_ready": all_ready,
        },
        "policies": results,
        "decision": "ready_to_retire_legacy_fallback" if all_ready else "keep_legacy_fallback",
        "automatic_change_allowed": False,
        "human_review_required": all_ready,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Teams recipient-policy endpoints using dry-run payloads"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--policy", action="append", dest="policies")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(
        base_url=args.base_url,
        policies=args.policies or list(DEFAULT_POLICIES),
        timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Teams recipient-policy readiness: "
        f"decision={report['decision']} "
        f"ready={report['summary']['ready_policies']}/"
        f"{report['summary']['policies_checked']}"
    )
    if args.strict and not report["summary"]["all_policies_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
